@echo off
REM Deploy frontend to S3 static website hosting (Windows).
REM
REM Originally this served the frontend through CloudFront with a private S3
REM origin. A real terraform apply against the AWS Academy Learner Lab
REM account hit AccessDenied on cloudfront:CreateOriginAccessControl, the
REM legacy cloudfront:CreateCloudFrontOriginAccessIdentity, and finally
REM cloudfront:CreateDistribution itself -- the Learner Lab's voclabs role
REM grants no CloudFront distribution-creation permission at all. See the
REM long comment on aws_s3_bucket_public_access_block.frontend in
REM infra/frontend.tf for the full explanation. This script now targets the
REM S3 static website endpoint directly (plain HTTP, no CDN, no HTTPS)
REM instead of a CloudFront domain, and there's no distribution to
REM invalidate.

setlocal enabledelayedexpansion

echo Reading Terraform outputs...
cd infra
for /f "delims=" %%i in ('terraform output -raw api_endpoint 2^>nul') do set API_URL=%%i
for /f "delims=" %%i in ('terraform output -raw frontend_bucket 2^>nul') do set BUCKET=%%i
for /f "delims=" %%i in ('terraform output -raw frontend_website_endpoint 2^>nul') do set WEBSITE_ENDPOINT=%%i
for /f "delims=" %%i in ('terraform output -raw cognito_user_pool_id 2^>nul') do set USER_POOL_ID=%%i
for /f "delims=" %%i in ('terraform output -raw cognito_spa_client_id 2^>nul') do set SPA_CLIENT_ID=%%i
cd ..

if "!BUCKET!"=="" (
  echo Error: Could not get S3 bucket name from Terraform outputs -- did you run "terraform apply" in infra\ yet?
  exit /b 1
)

REM Bake the real API endpoint + Cognito IDs into the static export at build
REM time (NEXT_PUBLIC_* vars are inlined by Next.js during "next build", not
REM read at runtime -- this is a static export, there's no server to read
REM them from later). Overwrites frontend\.env.local; your local-dev values
REM there are gitignored anyway, so this is safe to run repeatedly.
(
  echo NEXT_PUBLIC_API_URL=!API_URL!
  echo NEXT_PUBLIC_COGNITO_USER_POOL_ID=!USER_POOL_ID!
  echo NEXT_PUBLIC_COGNITO_CLIENT_ID=!SPA_CLIENT_ID!
) > frontend\.env.local

echo Building Next.js frontend (API=!API_URL!, Cognito pool=!USER_POOL_ID!)...
cd frontend
call npm install
call npm run build
cd ..

echo Uploading to S3...
aws s3 sync frontend\out\ s3://!BUCKET!/ --delete --cache-control "public, max-age=3600"

echo.
echo =========================================
echo Frontend deployed successfully!
echo URL: http://!WEBSITE_ENDPOINT!
echo (plain HTTP, no CDN/HTTPS -- see infra/frontend.tf comment for why)
echo =========================================
