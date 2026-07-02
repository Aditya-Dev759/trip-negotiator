variable "aws_region" {
  default = "us-east-1"
  type    = string
  # Left as us-east-1 because AWS Academy Learner Lab accounts are commonly
  # restricted to this region (LabRole/IAM often can't act outside it). Worth
  # flagging in the report's Sustainability section anyway: AWS's own
  # sustainability guidance points to regions with greener/renewable-heavy
  # grids (e.g. us-west-2, eu-west-1) as lower marginal carbon intensity per
  # request than us-east-1 -- this is a "would do differently in production,
  # can't in the lab" item, not an oversight.
  description = "AWS region for resources"
}

variable "project_name" {
  default     = "tripnegotiator"
  type        = string
  description = "Project name prefix for all resources"
}

variable "environment" {
  default     = "dev"
  type        = string
  description = "Environment name"
}

variable "groq_api_key" {
  type        = string
  sensitive   = true
  description = "Groq API key (store in environment or Terraform variables)"
}

variable "cognito_user_email" {
  type        = string
  description = "Initial Cognito user email for testing"
}

variable "max_negotiation_rounds" {
  default     = 3
  type        = number
  description = "Maximum negotiation rounds before force-finalize"
}

variable "lambda_image_tag" {
  default     = "latest"
  type        = string
  description = "Tag of the container image in ECR (see ecr.tf) to deploy for the api/itinerary_agent/budget_agent/logistics_agent/booking_agent Lambdas. Push a new image with build-lambda-image.sh, then terraform apply to roll it out."
}

variable "enable_auth" {
  default     = true
  type        = bool
  description = "Gate POST /trips behind the Cognito JWT authorizer (cognito.tf). Defaults on now that the frontend implements a real sign-up/sign-in flow (frontend/src/lib/auth.ts) and attaches the resulting ID token as a Bearer header (frontend/src/lib/api.ts). Set to false to demo without the login screen if needed."
}

variable "alert_email" {
  type        = string
  default     = ""
  description = "Email address for CloudWatch alarm / budget threshold notifications (monitoring.tf, budgets.tf). Leave blank to skip creating the SNS email subscription and budget notification."
}
