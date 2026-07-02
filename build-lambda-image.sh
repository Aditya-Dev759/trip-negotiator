#!/usr/bin/env bash
# Builds Dockerfile.lambda for linux/arm64 (matches the Graviton `architectures
# = ["arm64"]` setting on the container-image Lambdas in infra/lambda.tf --
# see that file for the cost/sustainability rationale) and pushes it to the
# ECR repository Terraform creates (infra/ecr.tf).
#
# Bootstrap ordering (container-image Lambdas can't be created until an image
# already exists in the repo):
#   1. terraform apply -target=aws_ecr_repository.lambda_image   (creates just the repo)
#   2. bash build-lambda-image.sh                                (this script)
#   3. terraform apply                                           (creates/updates the Lambdas)
# Re-run steps 2-3 alone for future code changes.
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-tripnegotiator}"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${1:-latest}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-lambda"

echo "Logging in to ECR: ${REPO_URI}"
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Building ${REPO_URI}:${IMAGE_TAG} (linux/arm64)"
docker buildx build --platform linux/arm64 -f Dockerfile.lambda -t "${REPO_URI}:${IMAGE_TAG}" --push .

echo "Pushed ${REPO_URI}:${IMAGE_TAG}"
echo "Now run: cd infra && terraform apply"
