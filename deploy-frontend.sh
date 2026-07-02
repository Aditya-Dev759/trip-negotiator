#!/bin/bash
# Deploy frontend to S3 + CloudFront
set -e

echo "Reading Terraform outputs..."
cd infra
API_URL=$(terraform output -raw api_endpoint 2>/dev/null || echo "")
BUCKET=$(terraform output -raw frontend_bucket 2>/dev/null || echo "")
DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
DOMAIN=$(terraform output -raw cloudfront_domain 2>/dev/null || echo "")
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id 2>/dev/null || echo "")
SPA_CLIENT_ID=$(terraform output -raw cognito_spa_client_id 2>/dev/null || echo "")
cd ..

if [ -z "$BUCKET" ]; then
  echo "Error: Could not get S3 bucket name from Terraform outputs -- did you run 'terraform apply' in infra/ yet?"
  exit 1
fi

# Bake the real API endpoint + Cognito IDs into the static export at build
# time (NEXT_PUBLIC_* vars are inlined by Next.js during `next build`, not
# read at runtime -- this is a static export, there's no server to read
# them from later). Overwrites frontend/.env.local; your local-dev values
# there are gitignored anyway, so this is safe to run repeatedly.
cat > frontend/.env.local << ENVEOF
NEXT_PUBLIC_API_URL=${API_URL}
NEXT_PUBLIC_COGNITO_USER_POOL_ID=${USER_POOL_ID}
NEXT_PUBLIC_COGNITO_CLIENT_ID=${SPA_CLIENT_ID}
ENVEOF

echo "Building Next.js frontend (API=$API_URL, Cognito pool=$USER_POOL_ID)..."
cd frontend
npm install
npm run build   # next.config.js has output: 'export', so this alone produces out/
cd ..

echo "Uploading to S3..."
aws s3 sync frontend/out/ s3://$BUCKET/ --delete --cache-control "public, max-age=3600"

if [ -z "$DISTRIBUTION_ID" ]; then
  echo "Warning: Could not get CloudFront distribution ID -- skipping cache invalidation"
else
  echo "Invalidating CloudFront cache..."
  aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
fi

echo ""
echo "========================================="
echo "Frontend deployed successfully!"
echo "URL: https://$DOMAIN"
echo "========================================="
