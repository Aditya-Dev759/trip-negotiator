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
# --provenance=false --sbom=false: Buildx 0.10+ attaches build provenance/SBOM
# attestations to pushed images by default, which wraps the image in a
# multi-manifest (OCI image index) format. AWS Lambda's container runtime
# rejects that with "image manifest, config or layer media type ... is not
# supported" even though the image itself is fine and `docker pull`/`run`
# handle it without issue -- this only surfaced once a real `terraform apply`
# tried to create a Lambda function from the pushed image.
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f Dockerfile.lambda -t "${REPO_URI}:${IMAGE_TAG}" --push .

echo "Pushed ${REPO_URI}:${IMAGE_TAG}"
echo "Now run: cd infra && terraform apply"
