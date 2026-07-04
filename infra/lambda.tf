# Lambda functions.
#
# Split into two deployment styles, deliberately:
#   1. Container image (aws_ecr_repository.lambda_image, built from
#      ../Dockerfile.lambda) for every function that imports a third-party
#      package: the "api" function (FastAPI + Mangum, the single HTTP
#      entrypoint -- see api/main.py's own docstring) and the four
#      negotiation agents that call shared.web_search (which imports ddgs).
#      This replaces an earlier zip-based approach that only bundled
#      hand-picked .py files and never actually installed ddgs/fastapi/mangum
#      -- it would have failed with ModuleNotFoundError on first real invoke.
#   2. Plain zip (data.archive_file, unchanged pattern) for "supervisor",
#      which only touches shared.dynamo_utils/shared.s3_utils and boto3
#      (already present in the Lambda Python runtime) -- no reason to pay for
#      a container pull on every cold start when a 2KB zip works fine.
#
# All functions run on arm64 (Graviton2): ~20% cheaper and lower energy per
# request than x86_64 for the same work, per AWS's own Graviton benchmarks --
# this is this project's main concrete Sustainability-pillar decision.
# Dockerfile.lambda / build-lambda-image.sh build specifically for arm64 to
# match.

data "archive_file" "supervisor_lambda" {
  type        = "zip"
  output_path = "${path.module}/lambdas/supervisor.zip"

  source {
    content  = file("${path.module}/../agents/supervisor/handler.py")
    filename = "handler.py"
  }
  source {
    content  = file("${path.module}/../shared/__init__.py")
    filename = "shared/__init__.py"
  }
  source {
    content  = file("${path.module}/../shared/dynamo_utils.py")
    filename = "shared/dynamo_utils.py"
  }
  source {
    content  = file("${path.module}/../shared/s3_utils.py")
    filename = "shared/s3_utils.py"
  }
  # agents/supervisor/handler.py does `from shared.logging_utils import
  # get_logger` -- this file was missing from the zip's hand-picked file
  # list (added after this list was first written), so every real
  # invocation of the supervisor Lambda failed at import time with
  # "Runtime.ImportModuleError: No module named 'shared.logging_utils'".
  # This only surfaced once a negotiation actually reached the Finalize
  # state in Step Functions -- CheckConvergence routes there once
  # allApproved is true or round >= 3, so short/simple negotiations hit it
  # immediately. Stdlib-only (logging/os/sys), safe to bundle directly.
  source {
    content  = file("${path.module}/../shared/logging_utils.py")
    filename = "shared/logging_utils.py"
  }
}

resource "aws_lambda_function" "supervisor" {
  filename = data.archive_file.supervisor_lambda.output_path
  # Without this, `filename` is just a local path string that never changes
  # even when the zip's actual contents do, so Terraform has no signal to
  # ever call UpdateFunctionCode -- confirmed for real: adding
  # shared/logging_utils.py to the archive_file source list above produced a
  # genuinely different zip (different data.archive_file.supervisor_lambda
  # id/hash on refresh), but `terraform apply` still reported "No changes.
  # Your infrastructure matches the configuration." and the supervisor
  # Lambda kept running the old broken code that was missing that import.
  # source_code_hash gives Terraform the actual content hash to diff against.
  source_code_hash = data.archive_file.supervisor_lambda.output_base64sha256
  function_name     = "${var.project_name}-supervisor"
  role              = data.aws_iam_role.lab_role.arn
  handler           = "handler.lambda_handler"
  runtime           = "python3.11"
  architectures     = ["arm64"]
  timeout           = 30
  memory_size       = 256

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.trip_negotiations.name
      S3_BUCKET      = aws_s3_bucket.trip_data.id
      REGION         = var.aws_region
    }
  }

  depends_on = [data.archive_file.supervisor_lambda]

  tags = local.common_tags
}

# --- Container-image Lambdas ---------------------------------------------
# NOTE on bootstrap ordering: these resources reference
# aws_ecr_repository.lambda_image but Lambda requires an image to already
# exist at that URI before the function can be created. First-time deploy is
# therefore three steps, not one -- see build-lambda-image.sh for the exact
# commands:
#   1. terraform apply -target=aws_ecr_repository.lambda_image
#   2. build-lambda-image.sh   (builds Dockerfile.lambda, pushes :latest)
#   3. terraform apply         (creates these functions now that an image exists)

locals {
  lambda_image = "${aws_ecr_repository.lambda_image.repository_url}:${var.lambda_image_tag}"

  # Shared env vars every agent Lambda needs for live web-grounded search,
  # negotiation state, and reference data.
  agent_env = {
    DYNAMODB_TABLE          = aws_dynamodb_table.trip_negotiations.name
    S3_BUCKET               = aws_s3_bucket.trip_data.id
    REGION                  = var.aws_region
    SSM_GROQ_KEY_PARAM      = aws_ssm_parameter.groq_key.name
    MAX_NEGOTIATION_ROUNDS  = var.max_negotiation_rounds
  }
}

resource "aws_lambda_function" "api" {
  package_type  = "Image"
  image_uri     = local.lambda_image
  function_name = "${var.project_name}-api"
  role          = data.aws_iam_role.lab_role.arn
  architectures = ["arm64"]
  timeout       = 30
  memory_size   = 512

  image_config {
    command = ["api.main.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      DYNAMODB_TABLE     = aws_dynamodb_table.trip_negotiations.name
      S3_BUCKET          = aws_s3_bucket.trip_data.id
      REGION             = var.aws_region
      SSM_GROQ_KEY_PARAM = aws_ssm_parameter.groq_key.name
      STATE_MACHINE_ARN  = aws_sfn_state_machine.trip_negotiation.arn
      # Restricts FastAPI's CORSMiddleware to real origins in AWS instead of
      # the "*" used for local dev -- see api/main.py. Comma-separated.
      # http, not https: the frontend is served from a plain S3 static
      # website endpoint, not CloudFront (see infra/frontend.tf for why).
      ALLOWED_ORIGINS = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint},http://localhost:3000"
      # Tells Mangum to strip this stage prefix ("/dev") from the incoming
      # API Gateway path before handing it to FastAPI's router -- without
      # this, every route except POST /trips 404s, because FastAPI never
      # sees a route matching "/dev/locations/search" etc. See api/main.py's
      # Mangum handler comment for the full explanation.
      API_GATEWAY_STAGE = var.environment
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "itinerary_agent" {
  package_type  = "Image"
  image_uri     = local.lambda_image
  function_name = "${var.project_name}-itinerary-agent"
  role          = data.aws_iam_role.lab_role.arn
  architectures = ["arm64"]
  timeout       = 60
  memory_size   = 512

  image_config {
    command = ["agents.itinerary_agent.handler.lambda_handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.agent_env
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "budget_agent" {
  package_type  = "Image"
  image_uri     = local.lambda_image
  function_name = "${var.project_name}-budget-agent"
  role          = data.aws_iam_role.lab_role.arn
  architectures = ["arm64"]
  timeout       = 60
  memory_size   = 512

  image_config {
    command = ["agents.budget_agent.handler.lambda_handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.agent_env
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "logistics_agent" {
  package_type  = "Image"
  image_uri     = local.lambda_image
  function_name = "${var.project_name}-logistics-agent"
  role          = data.aws_iam_role.lab_role.arn
  architectures = ["arm64"]
  timeout       = 60
  memory_size   = 512

  image_config {
    command = ["agents.logistics_agent.handler.lambda_handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.agent_env
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "booking_agent" {
  package_type  = "Image"
  image_uri     = local.lambda_image
  function_name = "${var.project_name}-booking-agent"
  role          = data.aws_iam_role.lab_role.arn
  architectures = ["arm64"]
  timeout       = 60
  memory_size   = 512

  image_config {
    command = ["agents.booking_agent.handler.lambda_handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.agent_env
  }

  tags = local.common_tags
}

output "lambda_functions" {
  value = {
    api              = aws_lambda_function.api.function_name
    itinerary_agent  = aws_lambda_function.itinerary_agent.function_name
    budget_agent     = aws_lambda_function.budget_agent.function_name
    logistics_agent  = aws_lambda_function.logistics_agent.function_name
    booking_agent    = aws_lambda_function.booking_agent.function_name
    supervisor       = aws_lambda_function.supervisor.function_name
  }
}
