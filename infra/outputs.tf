output "project_summary" {
  value = {
    project_name       = var.project_name
    region             = var.aws_region
    environment        = var.environment
    dynamodb_table     = aws_dynamodb_table.trip_negotiations.name
    s3_bucket          = aws_s3_bucket.trip_data.id
    account_id         = data.aws_caller_identity.current.account_id
  }
  description = "TripNegotiator project summary"
}
