# TripNegotiator - Quick Start Guide

## What's Completed ✅

### Phase 1: Infrastructure & Setup
- ✅ Complete project scaffolding (12 directories)
- ✅ All Terraform IaC files (14 .tf files)
- ✅ AWS services configured (DynamoDB, S3, Lambda, Step Functions, API Gateway, Cognito, CloudFront)
- ✅ Reference data (destinations, costs, visa rules, seasonal notes)
- ✅ Shared utilities (Groq API client, DynamoDB operations, S3 loader)
- ✅ Git repository with 3 commits

### Phase 1.5: Local Testing
- ✅ Mock agent implementations
- ✅ Two passing test scenarios
- ✅ Local AWS mocking (moto)
- ✅ Test validation infrastructure

### Phase 2: Frontend UI
- ✅ Next.js 14 application (TypeScript + Tailwind CSS)
- ✅ React components:
  - TripForm: Collect trip preferences (destination, budget, duration, interests, tier, passport)
  - NegotiationProgress: Real-time negotiation tracking with polling
  - TripHistory: View past trips and their status
- ✅ API client with proper typing (Axios + TypeScript interfaces)
- ✅ Responsive design (mobile + desktop)

### Phase 2.5: Frontend Deployment
- ✅ S3 + CloudFront infrastructure (frontend.tf)
- ✅ Deployment scripts (Linux/Mac/Windows)
- ✅ Environment configuration
- ✅ FRONTEND_DEPLOYMENT.md guide

## Next Steps 🚀

### Step 1: Prepare AWS Credentials (5 min)

```bash
# Set environment variables for your Learner Lab or AWS account
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."  # If using Learner Lab

# Verify credentials
aws sts get-caller-identity
```

### Step 2: Deploy Infrastructure to AWS (10-15 min)

```bash
cd infra

# Review plan
terraform plan

# Apply
terraform apply

# Capture outputs (you'll need these for frontend)
terraform output
```

This creates all AWS resources. Costs:
- DynamoDB on-demand: $0 (free tier covers demo)
- Lambda: ~$0 (1M free invocations)
- API Gateway: ~$0 (< 1M calls)
- CloudFront: ~$0 (< 1GB)
- **Total**: < $1 for full demo

### Step 3: Test Backend Locally (5 min)

```bash
# From project root
python -m pytest tests/test_negotiation.py -v

# Expected: 2 PASSED
```

### Step 4: Deploy Frontend (5 min)

```bash
# From project root
bash deploy-frontend.sh     # Linux/Mac
deploy-frontend.bat         # Windows

# Outputs CloudFront URL where frontend is live
```

### Step 5: Configure Frontend API Integration (2 min)

```bash
# Get your API Gateway URL from Terraform outputs
cd infra
terraform output api_endpoint_url

# Update frontend/.env.local
NEXT_PUBLIC_API_URL=<your-api-gateway-url>
```

### Step 6: Test End-to-End Locally (5 min)

```bash
cd frontend
npm install
npm run dev

# Visit http://localhost:3000
# Submit a trip form → See "Negotiation in progress..."
# (Backend will return mock agents for now)
```

## What Happens Next (Phase 3) 🔄

### Phase 3: Real Lambda Implementation

Replace placeholder Lambda handlers with actual Groq integration:

1. **itinerary_agent/handler.py**: Call Groq to propose itineraries based on preferences
2. **budget_agent/handler.py**: Call Groq to validate budget and request revisions if needed
3. **logistics_agent/handler.py**: Call Groq to check travel feasibility (weather, closures)
4. **booking_agent/handler.py**: Call Groq to validate visa/passport requirements
5. **supervisor/handler.py**: Call Groq to finalize and score the plan

Each agent will:
- Read DynamoDB trip state and previous rounds
- Call `shared.groq_client.call_groq()` with system prompt
- Write verdict back to DynamoDB
- Return to Step Functions orchestrator

### Phase 4: Production Polish

- Add authentication (Cognito integration in frontend)
- Error handling and retry logic
- Logging and monitoring (CloudWatch)
- Cost optimization (Lambda reserved concurrency, caching strategies)
- Multi-region deployment

## Architecture Overview

```
Browser (Next.js Frontend)
    ↓ HTTPS
CloudFront CDN
    ↓
S3 (Static Files)
    ↓
API Gateway
    ↓
Lambda (trip-init)
    ↓
Step Functions Orchestrator
    ├→ Itinerary Agent Lambda → Groq API
    ├→ Budget Agent Lambda → Groq API
    ├→ Logistics Agent Lambda → Groq API
    └→ Booking Agent Lambda → Groq API
    ↓
DynamoDB (State Storage)
```

## File Structure Reference

```
trip-negotiator/
├── agents/               # Lambda handlers (PHASE 3: Add real Groq integration)
├── frontend/             # Next.js 14 UI (Phase 2: COMPLETE ✅)
├── shared/               # Python utilities (Phase 1: COMPLETE ✅)
├── data/                 # Reference data (Phase 1: COMPLETE ✅)
├── infra/                # Terraform IaC (Phase 1.5: COMPLETE ✅)
├── tests/                # Unit tests (Phase 1.5: COMPLETE ✅)
├── deploy-*.sh/.bat      # Deployment scripts (Phase 2.5: COMPLETE ✅)
└── README.md
```

## Troubleshooting

### Terraform Apply Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check you're in the right directory
pwd  # Should be .../trip-negotiator/infra

# Try again with more verbose output
terraform apply -auto-approve -var-file=terraform.tfvars
```

### Frontend Won't Connect to API

```bash
# Check .env.local has correct API URL
cat frontend/.env.local

# Check API Gateway is deployed
aws apigateway get-rest-apis --region us-east-1
```

### Tests Fail Locally

```bash
# Make sure virtualenv is activated
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt

# Run tests
pytest tests/test_negotiation.py -v
```

## Cost Tracking

Monitor your AWS costs:

```bash
# Recent costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics "BlendedCost"
```

## Useful Commands

```bash
# View all resources created
terraform state list

# Remove everything and start fresh
terraform destroy

# View DynamoDB contents
aws dynamodb scan --table-name tripnegotiator-trips

# Stream frontend logs
aws cloudfront list-distributions

# Monitor Lambda execution
aws logs tail /aws/lambda/tripnegotiator-trip-init --follow
```

## Next Meeting Checklist

- [ ] Deploy infrastructure to AWS
- [ ] Test frontend deployment to CloudFront
- [ ] Implement Phase 3 Lambda handlers with Groq
- [ ] Test end-to-end negotiation flow
- [ ] Set up Cognito authentication
- [ ] Configure custom domain (optional)
- [ ] Set up monitoring and alerts

## Questions?

- AWS Services: See README.md for architecture diagrams
- Frontend Code: See frontend/README.md
- Infrastructure: See infra/ directory with inline comments
- Testing: See tests/test_negotiation.py for mock agent behavior

---

**Ready to deploy?** Start with Step 1 → Step 6 above. Total time: ~40 minutes for full setup.
