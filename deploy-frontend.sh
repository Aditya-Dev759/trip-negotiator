#!/bin/bash
# Deploy frontend to S3 static website hosting.
#
# Originally this served the frontend through CloudFront with a private S3
# origin. A real `terraform apply` against the AWS Academy Learner Lab
# account hit AccessDenied on cloudfront:CreateOriginAccessControl, the
# legacy cloudfront:CreateCloudFrontOriginAccessIdentity, and finally
# cloudfront:CreateDistribution itself -- the Learner Lab's `voclabs` role
# grants no CloudFront distribution-creation permission at all. See the long
# comment on aws_s3_bucket_public_access_block.frontend in infra/frontend.tf
# for the full explanation. This script now targets the S3 static website
# endpoint directly (plain HTTP, no CDN, no HTTPS) instead of a CloudFront
# domain, and there's no distribution to invalidate.
set -e

echo "Reading Terraform outputs..."
cd infra
API_URL=$(terraform output -raw api_endpoint 2>/dev/null || echo "")
BUCKET=$(terraform output -raw frontend_bucket 2>/dev/null || echo "")
WEBSITE_ENDPOINT=$(terraform output -raw frontend_website_endpoint 2>/dev/null || echo "")
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

# Force a fully clean build. NEXT_PUBLIC_* vars are inlined into the JS
# bundle at build time -- if frontend/.next/ still has cache from an
# earlier build (e.g. local `npm run dev` testing, which intentionally
# leaves the Cognito vars blank to disable the login gate locally),
# Next.js can carry stale inlined values into a later production build,
# silently shipping a bundle where AUTH_ENABLED evaluates false even
# though .env.local now has real values. This bit us once already: the
# deployed site skipped the login screen entirely and POST /trips came
# back 401 from the API Gateway JWT authorizer, which was still correctly
# enforcing auth the frontend never attempted.
if [ -d "frontend/.next" ]; then
  echo "Clearing stale Next.js build cache..."
  rm -rf frontend/.next
fi

echo "Building Next.js frontend (API=$API_URL, Cognito pool=$USER_POOL_ID)..."
cd frontend
npm install
npm run build   # next.config.js has output: 'export', so this alone produces out/
cd ..

echo "Uploading to S3..."
aws s3 sync frontend/out/ s3://$BUCKET/ --delete --cache-control "public, max-age=3600"

echo ""
echo "========================================="
echo "Frontend deployed successfully!"
echo "URL: http://$WEBSITE_ENDPOINT"
echo "(plain HTTP, no CDN/HTTPS -- see infra/frontend.tf comment for why)"
echo "========================================="
