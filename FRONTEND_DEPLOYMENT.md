# TripNegotiator Frontend Deployment Configuration

## Architecture

```
User -> S3 Static Website Hosting -> API Gateway -> Lambda Agents
```

**Note:** this originally served the frontend through CloudFront in front of
a private S3 bucket. A real `terraform apply` against the AWS Academy
Learner Lab account was denied on `cloudfront:CreateOriginAccessControl`,
the legacy `cloudfront:CreateCloudFrontOriginAccessIdentity`, and finally
`cloudfront:CreateDistribution` itself -- the Learner Lab's `voclabs` role
grants no CloudFront distribution-creation permission at all. See the long
comment on `aws_s3_bucket_public_access_block.frontend` in
`infra/frontend.tf` for the full explanation and the production fix. The
frontend now serves directly from the S3 bucket's own static website
endpoint: plain HTTP, no CDN, no HTTPS, no edge caching.

## Deployment Flow

1. **Build**: Next.js exports to static HTML/CSS/JS (`output: 'export'` in `next.config.js`, so `next build` alone produces `frontend/out/`)
2. **Upload**: Static files -> S3 bucket (versioned, public-read via bucket policy -- see the trade-off note above)
3. **Serve**: S3's native static website hosting serves `index.html` directly over HTTP
4. **API**: Frontend calls API Gateway for trip planning

## Files & Costs

- **S3**: ~$0.01/month for static files (< 100MB) plus negligible request/egress cost at demo volume
- **No CloudFront charge** since it isn't used in this account

## Deployment Steps

### One-time Setup (after Terraform apply)

```bash
cd infra
terraform output frontend_bucket
terraform output frontend_website_endpoint
```

### Deploy Frontend

```bash
# Using script (recommended) -- reads Terraform outputs, bakes them into
# frontend/.env.local, builds, and syncs to S3 automatically.
bash deploy-frontend.sh    # Linux/Mac/Git Bash
deploy-frontend.bat        # Windows (PowerShell/cmd)

# Or manual steps
cd frontend
npm install
npm run build   # produces frontend/out/ directly, no separate export step
cd ..
aws s3 sync frontend/out/ s3://BUCKET_NAME/ --delete
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
# View S3 bucket contents
aws s3 ls s3://BUCKET_NAME/ --recursive

# Website endpoint URL
terraform -chdir=infra output -raw frontend_website_endpoint
```

## Rollback

```bash
# S3 versioning is enabled (infra/frontend.tf), so a previous object version
# can be restored directly, or just redeploy the previous frontend build.
aws s3api list-object-versions --bucket BUCKET_NAME --prefix index.html
```
