# S3 bucket for frontend static files
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-frontend-${data.aws_caller_identity.current.account_id}"

  tags = local.common_tags
}

# Public-access-block settings for the frontend bucket.
#
# This project originally kept this bucket fully private and served it
# through CloudFront with Origin Access Control. A real `terraform apply`
# against the AWS Academy Learner Lab account hit AccessDenied on both
# cloudfront:CreateOriginAccessControl and the legacy
# cloudfront:CreateCloudFrontOriginAccessIdentity, and then on
# cloudfront:CreateDistribution itself -- the Learner Lab's `voclabs` role
# grants no CloudFront distribution-creation permissions at all, not just
# the origin-access sub-permissions. That rules out a CDN-fronted private
# bucket entirely in this account.
#
# The fallback used here is native S3 static website hosting: the bucket
# serves index.html directly over its own public HTTP website endpoint, no
# CloudFront involved. This still requires public GetObject on the bucket
# (no List, no Write, no Delete, ACLs stay blocked) -- a real, documented
# trade-off from a genuine Learner Lab platform restriction, not an
# oversight. In an unrestricted production account this would revert to a
# fully private bucket behind CloudFront + Origin Access Control exactly as
# infra/frontend.tf originally defined it.
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

# Enable versioning for rollbacks
resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Every deploy-frontend.sh run overwrites the same keys -- without this,
# every previous build's noncurrent versions pile up in this bucket forever.
resource "aws_s3_bucket_lifecycle_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    # Empty filter = applies to every object in the bucket. The provider
    # currently accepts a rule with no filter/prefix at all (just a
    # deprecation warning), but a future version rejects it outright, so
    # this is made explicit here now that a real apply actually surfaced it.
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Native S3 static website hosting -- this is what actually serves the
# frontend now that CloudFront is unavailable in this account. index.html
# doubles as the SPA fallback for client-side routing (error_document also
# points at it, since this is a single-page app and every route needs to
# resolve to the same index.html).
resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

# Public-read bucket policy: GetObject only, from anyone. See the long
# comment on aws_s3_bucket_public_access_block.frontend above for why this
# bucket can't be kept fully private under Learner Lab's IAM restrictions.
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadOnly"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.id
}

output "frontend_website_endpoint" {
  value       = aws_s3_bucket_website_configuration.frontend.website_endpoint
  description = "Plain-HTTP S3 static website URL -- no CloudFront/HTTPS in this Learner Lab account (see aws_s3_bucket_public_access_block.frontend comment)"
}
