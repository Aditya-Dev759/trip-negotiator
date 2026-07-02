@echo off
REM Deploy entire TripNegotiator infrastructure and frontend to AWS (Windows)

setlocal enabledelayedexpansion

echo.
echo ===================================
echo TripNegotiator Full Deployment
echo ===================================
echo.

echo Step 1: Deploying AWS infrastructure (Terraform)...
cd infra
call terraform init
call terraform plan -out=tfplan
call terraform apply tfplan
cd ..

echo.
echo Step 2: Deploying frontend to S3 + CloudFront...
call deploy-frontend.bat

echo.
echo ===================================
echo Deployment complete!
echo ===================================
echo.
echo Next steps:
echo 1. Update frontend\.env.local with your API Gateway URL
echo 2. Implement Phase 2 Lambda agents with Groq integration
echo 3. Wire up API Gateway routes to Lambda functions
echo 4. Test end-to-end negotiation flow
