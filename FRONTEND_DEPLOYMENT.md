# TripNegotiator Frontend Deployment Configuration

## Architecture

```
User → CloudFront (CDN) → S3 (Static Files) → API Gateway → Lambda Agents
```

## Deployment Flow

1. **Build**: Next.js exports to static HTML/CSS/JS
2. **Upload**: Static files → S3 bucket (versioned, private)
3. **Serve**: CloudFront CDN distributes globally with caching
4. **API**: Frontend calls API Gateway for trip planning

## Files & Costs

- **S3**: ~$0.01/month for static files (< 100MB)
- **CloudFront**: ~$0.085/GB egress (demo usage << $1)
- **Total**: ~$2-3/month in production

## Deployment Steps

### One-time Setup (after Terraform apply)

```bash
# Get outputs from Terraform
cd infra
terraform output frontend_bucket
terraform output cloudfront_domain
terraform output cloudfront_distribution_id
```

### Deploy Frontend

```bash
# Using script (recommended)
bash deploy-frontend.sh   # Linux/Mac
deploy-frontend.bat       # Windows

# Or manual steps
cd frontend
npm install
npm run build
npm run export
aws s3 sync out/ s3://BUCKET_NAME/ --delete
aws cloudfront create-invalidation --distribution-id DIST_ID --paths "/*"
```

### Configure API Integration

```bash
# Copy env template
cp frontend/.env.local.example frontend/.env.local

# Edit with your API Gateway endpoint
NEXT_PUBLIC_API_URL=https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev
```

## Monitoring

```bash
# View S3 bucket
aws s3 ls s3://BUCKET_NAME/ --recursive

# Invalidate cache
aws cloudfront create-invalidation --distribution-id DIST_ID --paths "/*"

# View CloudFront stats
aws cloudfront get-distribution --id DIST_ID
```

## Rollback

```bash
# CloudFront caches for 1 hour by default
# To rollback: redeploy previous version + invalidate

# Or disable distribution (stop serving)
aws cloudfront delete-distribution --id DIST_ID
```
