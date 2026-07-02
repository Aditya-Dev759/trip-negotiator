@echo off
REM Builds Dockerfile.lambda for linux/arm64 and pushes it to the ECR repo
REM Terraform creates (infra/ecr.tf). See build-lambda-image.sh for the full
REM bootstrap-ordering explanation (ECR repo must exist before this runs;
REM Lambda functions can't be created until an image exists after this runs).

setlocal
if "%PROJECT_NAME%"=="" set PROJECT_NAME=tripnegotiator
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
set IMAGE_TAG=%1
if "%IMAGE_TAG%"=="" set IMAGE_TAG=latest

for /f "tokens=*" %%i in ('aws sts get-caller-identity --query Account --output text') do set ACCOUNT_ID=%%i
set REPO_URI=%ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%PROJECT_NAME%-lambda

echo Logging in to ECR: %REPO_URI%
aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin %ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com

echo Building %REPO_URI%:%IMAGE_TAG% (linux/arm64)
REM --provenance=false --sbom=false: Buildx 0.10+ attaches build provenance/SBOM
REM attestations to pushed images by default, which wraps the image in a
REM multi-manifest (OCI image index) format. AWS Lambda's container runtime
REM rejects that with "image manifest, config or layer media type ... is not
REM supported" even though the image itself is fine -- only surfaced once a
REM real `terraform apply` tried to create a Lambda function from the image.
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f Dockerfile.lambda -t %REPO_URI%:%IMAGE_TAG% --push .

echo Pushed %REPO_URI%:%IMAGE_TAG%
echo Now run: cd infra ^&^& terraform apply
endlocal
