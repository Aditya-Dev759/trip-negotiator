# Learner Lab provides LabRole — data source to reference it
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

output "lab_role_arn" {
  value = data.aws_iam_role.lab_role.arn
}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_region_name" {
  value = data.aws_region.current.name
}
