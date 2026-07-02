@echo off
REM Deploy frontend to S3 + CloudFront (Windows)

setlocal enabledelayedexpansion

echo Reading Terraform outputs...
cd infra
for /f "delims=" %%i in ('terraform output -raw api_endpoint 2^>nul') do set API_URL=%%i
for /f "delims=" %%i in ('terraform output -raw frontend_bucket 2^>nul') do set BUCKET=%%i
for /f "delims=" %%i in ('terraform output -raw cloudfront_distribution_id 2^>nul') do set DISTRIBUTION_ID=%%i
for /f "delims=" %%i in ('terraform output -raw cloudfront_domain 2^>nul') do set DOMAIN=%%i
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

if "!DISTRIBUTION_ID!"=="" (
  echo Warning: Could not get CloudFront distribution ID -- skipping cache invalidation
) else (
  echo Invalidating CloudFront cache...
  aws cloudfront create-invalidation --distribution-id !DISTRIBUTION_ID! --paths "/*"
)

echo.
echo =========================================
echo Frontend deployed successfully!
echo URL: https://!DOMAIN!
echo =========================================
