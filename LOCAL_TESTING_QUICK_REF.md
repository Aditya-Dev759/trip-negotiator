"""
Quick reference for local testing commands.

Copy & paste these commands to test locally without AWS.
"""

# =============================================================================
# Step 1: Create & activate virtual environment (One-time)
# =============================================================================

# Windows PowerShell:
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux:
python3 -m venv venv
source venv/bin/activate


# =============================================================================
# Step 2: Install dependencies
# =============================================================================

pip install --upgrade pip
pip install -r requirements.txt


# =============================================================================
# Step 3: Run local tests (NO AWS NEEDED!)
# =============================================================================

# Option A: Run with pytest (structured)
pytest tests/test_negotiation.py -v -s

# Option B: Run as demo (pretty output)
python tests/test_negotiation.py

# Option C: Run specific test
pytest tests/test_negotiation.py::TestMultiAgentNegotiation::test_successful_negotiation_round_1 -v -s


# =============================================================================
# Step 4: Run code quality checks
# =============================================================================

# Lint all code
flake8 agents/ shared/ tests/ --max-line-length=100

# Run all tests (if more added)
pytest tests/ -v


# =============================================================================
# What you'll see:
# =============================================================================

# ROUND 1 SUCCESSFUL NEGOTIATION:
#   User: "I want a cheap trip to Bali"
#   Itinerary Agent: "How about 7 days in Bali, budget tier"
#   Budget Agent: ✅ Approved "~$560 total, fits your $2000 budget"
#   Logistics Agent: ✅ Approved "No weather warnings"
#   Booking Agent: ✅ Approved "Passport valid"
#   Supervisor: ✅ FINALIZED "Trip approved!"
#
# ROUND 2 NEGOTIATION WITH REVISION:
#   User: "I want luxury trip to Tokyo for $500" (over-budget!)
#   Itinerary Agent: "How about luxury Tokyo"
#   Budget Agent: ❌ REJECTED "Tokyo luxury = $4000+ vs your $500"
#   Itinerary Agent (Round 2): "Adjusting to budget tier Tokyo"
#   Budget Agent: ✅ Approved "Budget Tokyo = $1000, still fits"
#   All agents: ✅ Approved
#   Supervisor: ✅ FINALIZED "Trip approved after negotiation!"


# =============================================================================
# Troubleshooting
# =============================================================================

# Q: "pytest: command not found"
# A: Make sure venv is activated: source venv/bin/activate (or .\venv\Scripts\Activate.ps1 on Windows)

# Q: "ImportError: No module named 'boto3'"
# A: Run "pip install -r requirements.txt" inside the activated venv

# Q: Tests are slow
# A: Normal - moto mocks are slower than real services. Real AWS will be faster.

# Q: Want to see actual AWS integration later?
# A: That's Phase 2. For now, these mocks prove the negotiation logic works.


# =============================================================================
# Next: Deploy to AWS
# =============================================================================

# Once tests pass locally:

# 1. Set up AWS credentials
#    export AWS_ACCESS_KEY_ID="..."
#    export AWS_SECRET_ACCESS_KEY="..."
#    export AWS_SESSION_TOKEN="..."

# 2. Create terraform.tfvars with your Groq key
#    cp infra/terraform.tfvars.example infra/terraform.tfvars
#    # Edit and fill in values

# 3. Deploy
#    cd infra
#    terraform init
#    terraform plan
#    terraform apply

# 4. Implement Phase 2 Lambda agents with real Groq calls
