resource "aws_ssm_parameter" "groq_key" {
  name      = "/${var.project_name}/groq-key"
  type      = "SecureString"
  value     = var.groq_api_key
  overwrite = true

  tags = local.common_tags
}

output "groq_key_parameter_name" {
  value = aws_ssm_parameter.groq_key.name
}
