resource "aws_s3_bucket" "trip_data" {
  bucket = "${var.project_name}-data-${data.aws_caller_identity.current.account_id}"
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "trip_data" {
  bucket = aws_s3_bucket.trip_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "trip_data" {
  bucket = aws_s3_bucket.trip_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload reference data files
resource "aws_s3_object" "destinations" {
  bucket = aws_s3_bucket.trip_data.id
  key    = "destinations.json"
  source = "${path.module}/../data/destinations.json"
  etag   = filemd5("${path.module}/../data/destinations.json")
}

resource "aws_s3_object" "cost_baselines" {
  bucket = aws_s3_bucket.trip_data.id
  key    = "cost_baselines.json"
  source = "${path.module}/../data/cost_baselines.json"
  etag   = filemd5("${path.module}/../data/cost_baselines.json")
}

resource "aws_s3_object" "visa_rules" {
  bucket = aws_s3_bucket.trip_data.id
  key    = "visa_rules.json"
  source = "${path.module}/../data/visa_rules.json"
  etag   = filemd5("${path.module}/../data/visa_rules.json")
}

resource "aws_s3_object" "seasonal_notes" {
  bucket = aws_s3_bucket.trip_data.id
  key    = "seasonal_notes.json"
  source = "${path.module}/../data/seasonal_notes.json"
  etag   = filemd5("${path.module}/../data/seasonal_notes.json")
}

# Added along with the exchange-rate feature (shared/currency_utils.py) --
# this was the one static reference file that never got an aws_s3_object
# entry, so the S3-first / local-fallback lookup in shared/s3_utils.py would
# have silently always fallen through to the copy bundled in the Lambda
# image instead of ever reading from S3 in AWS.
resource "aws_s3_object" "country_currencies" {
  bucket = aws_s3_bucket.trip_data.id
  key    = "country_currencies.json"
  source = "${path.module}/../data/country_currencies.json"
  etag   = filemd5("${path.module}/../data/country_currencies.json")
}

# Cost optimization: without this, every re-upload (e.g. reference-data
# edits) leaves the previous version around forever now that versioning is
# enabled above -- old versions/incomplete multipart uploads just accumulate
# storage cost with no retention purpose for reference data that's fully
# reproducible from the data/ directory in git.
resource "aws_s3_bucket_lifecycle_configuration" "trip_data" {
  bucket = aws_s3_bucket.trip_data.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

output "s3_bucket_name" {
  value = aws_s3_bucket.trip_data.id
}

output "s3_bucket_arn" {
  value = aws_s3_bucket.trip_data.arn
}
