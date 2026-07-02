# ECR repository backing the container-image Lambdas (api, itinerary_agent,
# budget_agent, logistics_agent, booking_agent). See ../Dockerfile.lambda and
# ../build-lambda-image.sh for why this project moved from zip-based Lambdas
# (which never actually bundled ddgs/fastapi/mangum) to one shared image.

resource "aws_ecr_repository" "lambda_image" {
  name                 = "${var.project_name}-lambda"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# Cost optimization: untagged images (left behind by repeated `:latest`
# pushes) expire after 7 days instead of accumulating in ECR storage forever.
resource "aws_ecr_lifecycle_policy" "lambda_image" {
  repository = aws_ecr_repository.lambda_image.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      }
    ]
  })
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.lambda_image.repository_url
  description = "Push images here (see build-lambda-image.sh) before applying the Lambda functions"
}
