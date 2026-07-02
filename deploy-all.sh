#!/bin/bash
# Deploy entire TripNegotiator infrastructure and frontend to AWS

set -e

echo "🚀 TripNegotiator Full Deployment"
echo "=================================="
echo ""

# Step 1: Deploy infrastructure
echo "Step 1: Deploying AWS infrastructure (Terraform)..."
cd infra
terraform init
terraform plan -out=tfplan
terraform apply tfplan
cd ..

echo ""
echo "Step 2: Deploying frontend to S3 + CloudFront..."
bash deploy-frontend.sh

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Update frontend/.env.local with your API Gateway URL"
echo "2. Implement Phase 2 Lambda agents with Groq integration"
echo "3. Wire up API Gateway routes to Lambda functions"
echo "4. Test end-to-end negotiation flow"
