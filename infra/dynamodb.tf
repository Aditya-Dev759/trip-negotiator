resource "aws_dynamodb_table" "trip_negotiations" {
  name           = "${var.project_name}-negotiations"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "PK"
  range_key      = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # Global Secondary Index for querying by user
  global_secondary_index {
    name            = "UserIdIndex"
    hash_key        = "userId"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expirationTime"
    enabled        = true
  }

  # Durability: continuous backups letting you restore to any point in the
  # last 35 days. This table is the only durable record of every
  # negotiation round (itinerary proposals, verdicts, objections) --
  # previously nothing protected it from an accidental delete/overwrite.
  point_in_time_recovery {
    enabled = true
  }

  # Explicit even though it matches the DynamoDB default (AWS owned key) --
  # states the Security-pillar position in code rather than leaving it
  # implicit. Swap to a customer-managed KMS key for stricter key-rotation
  # control in a production, non-Learner-Lab account.
  server_side_encryption {
    enabled = true
  }

  tags = local.common_tags
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.trip_negotiations.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.trip_negotiations.arn
}
