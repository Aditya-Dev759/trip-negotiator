# API Gateway + Lambda Integration
#
# Single proxy integration in front of aws_lambda_function.api (the
# FastAPI/Mangum app in api/main.py) handles every route -- GET /trips,
# GET /trips/{id}, GET /locations/search, GET /exchange-rate, GET /health,
# and FastAPI's own /docs -- since Mangum translates the API Gateway event
# into an ASGI request and FastAPI's own router does the dispatching. This
# replaces the previous setup, which pointed at a separate `trip_init`
# Lambda that hand-rolled the same routing/response-building logic FastAPI
# already does (and had drifted out of sync with api/main.py's actual
# routes, e.g. it never knew about /locations/search or /exchange-rate).
#
# POST /trips is called out as its own explicit route (rather than folded
# into the proxy) purely so it can be gated behind the Cognito JWT
# authorizer when var.enable_auth = true -- see cognito.tf. API Gateway
# always prefers an exact route match over a {proxy+} wildcard for the same
# request, so this doesn't change how any other path is handled.

resource "aws_apigatewayv2_api" "trip_api" {
  name          = "${var.project_name}-http-api"
  protocol_type = "HTTP"

  cors_configuration {
    # Restricted to the deployed frontend + local dev, not "*". The frontend
    # is served over plain HTTP from an S3 static website endpoint, not
    # HTTPS via CloudFront -- see infra/frontend.tf for why (CloudFront
    # distribution creation is denied entirely in this AWS Academy Learner
    # Lab account). The website endpoint is only known after that resource
    # is created, which Terraform resolves automatically via this reference.
    allow_origins = ["http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}", "http://localhost:3000"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["*"]
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.trip_api.id
  name        = var.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    # $context.error.type is a REST API (v1) only context variable -- HTTP
    # APIs (v2, what this project uses) reject it with "context variables
    # are not supported", which only surfaced once a real
    # aws_apigatewayv2_stage was actually applied. $context.error.message is
    # the HTTP API-supported equivalent and is kept.
    format = "$context.requestId $context.error.message $context.status $context.integrationErrorMessage"
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${var.project_name}-http-api"
  retention_in_days = 7

  tags = local.common_tags
}

resource "aws_apigatewayv2_integration" "api_integration" {
  api_id                 = aws_apigatewayv2_api.trip_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.arn
  payload_format_version = "2.0"
}

# Root path ("/") and every other path go through the catch-all proxy route,
# unauthenticated -- read endpoints (GET /trips, /locations/search,
# /exchange-rate) have no sensitive per-user data worth gating in a
# single-demo-user course project, and FastAPI's interactive /docs needs to
# stay reachable without a token.
resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.trip_api.id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.api_integration.id}"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.trip_api.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.api_integration.id}"
}

# Explicit POST /trips route so it can be individually gated behind Cognito
# (var.enable_auth) without affecting the routes above.
resource "aws_apigatewayv2_route" "post_trips" {
  api_id    = aws_apigatewayv2_api.trip_api.id
  route_key = "POST /trips"
  target    = "integrations/${aws_apigatewayv2_integration.api_integration.id}"

  authorization_type = var.enable_auth ? "JWT" : "NONE"
  authorizer_id       = var.enable_auth ? aws_apigatewayv2_authorizer.cognito[0].id : null
}

resource "aws_lambda_permission" "apigw_api" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.trip_api.execution_arn}/*/*"

  # Without this, `terraform apply -replace=aws_lambda_function.api` (needed
  # to force a container-image Lambda to actually re-pull a new :latest
  # digest -- see infra/lambda.tf's comment on image_uri) silently orphans
  # this grant: AWS deletes the function's resource-based policy the moment
  # the underlying function object is destroyed, but aws_lambda_function.api
  # keeps the same function_name/ARN after recreation, so this resource's own
  # inputs never change and Terraform has no reason to think it needs to be
  # re-applied. Every request then gets AWS's own AccessDenied on
  # lambda:InvokeFunction, which API Gateway surfaces to clients as a bare
  # {"message":"Internal Server Error"} -- no CloudWatch Lambda logs at all,
  # since the function is never actually invoked. Hit this twice for real
  # during deployment before adding this rule. replace_triggered_by forces
  # Terraform to recreate this permission in the same apply any time the
  # function it's attached to is replaced, regardless of whether this
  # resource's own arguments changed.
  lifecycle {
    replace_triggered_by = [aws_lambda_function.api]
  }
}

output "api_endpoint" {
  value       = "${aws_apigatewayv2_api.trip_api.api_endpoint}/${var.environment}"
  description = "API Gateway HTTP API endpoint"
}
