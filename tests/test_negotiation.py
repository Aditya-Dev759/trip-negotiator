"""
End-to-end local test of the TripNegotiator multi-agent negotiation flow.

This simulates a complete negotiation cycle:
  Round 1: Itinerary → Budget → Logistics → Booking → Check convergence
  If rejected: Loop back with objections
  Max 3 rounds → Force finalize

Run with: pytest tests/test_negotiation.py -v -s
Or run directly: python tests/test_negotiation.py
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tests.mock_agents import (
    MockItineraryAgent,
    MockBudgetAgent,
    MockLogisticsAgent,
    MockBookingAgent,
    SupervisorAgent,
)
from tests.local_test_utils import print_step


class TestMultiAgentNegotiation:
    """Test the multi-agent negotiation flow."""
    
    def test_successful_negotiation_round_1(self):
        """Test: User requests a cheap trip that passes all agents on round 1."""
        print_step(0, "Starting Negotiation - Cheap Trip to Bali")
        
        # User goal: cheap trip, good budget
        user_goal = {
            "destination": "Bali",
            "budget": 2000,  # Plenty of budget
            "length_days": 7,
            "interests": ["beach", "culture"],
            "budget_tier": "budget",
            "passport_valid_months": 12,
        }
        print_step(1, "User Submits Trip Request", user_goal)
        
        # Round 1: Itinerary Agent proposes
        itinerary_agent = MockItineraryAgent()
        itin_proposal = itinerary_agent.propose(user_goal, round_num=1)
        print_step(2, "Itinerary Agent Proposes", itin_proposal["proposal"])
        
        # Budget Agent reviews
        budget_agent = MockBudgetAgent()
        budget_verdict = budget_agent.review(itin_proposal["proposal"], user_goal)
        print_step(3, "Budget Agent Reviews", budget_verdict["proposal"])
        
        # Logistics Agent reviews
        logistics_agent = MockLogisticsAgent()
        logistics_verdict = logistics_agent.review(itin_proposal["proposal"])
        print_step(4, "Logistics Agent Reviews", logistics_verdict["proposal"])
        
        # Booking Agent reviews
        booking_agent = MockBookingAgent()
        booking_verdict = booking_agent.review(itin_proposal["proposal"], user_goal)
        print_step(5, "Booking Agent Reviews", booking_verdict["proposal"])
        
        # Supervisor checks convergence
        supervisor = SupervisorAgent()
        all_verdicts = [budget_verdict, logistics_verdict, booking_verdict]
        all_approved, objections = supervisor.check_convergence(all_verdicts)
        
        print_step(6, f"Convergence Check", {
            "all_approved": all_approved,
            "objections_count": len(objections),
        })
        
        # Assertions
        assert all_approved, "All agents should approve for cheap Bali trip"
        assert budget_verdict["proposal"]["status"] == "approved"
        assert logistics_verdict["proposal"]["status"] == "approved"
        assert booking_verdict["proposal"]["status"] == "approved"
        
        # Finalize
        final = supervisor.finalize(
            "trip-123",
            itin_proposal["proposal"],
            all_verdicts,
        )
        print_step(7, "FINALIZED - Trip Plan Approved!", {
            "destination": final["final_itinerary"]["destination"],
            "budget_ok": final["final_itinerary"]["daily_budget"],
            "status": final["status"],
        })
        
        assert final["status"] == "finalized"
        assert len(final["unresolved_objections"]) == 0
    
    def test_multi_round_negotiation_with_budget_rejection(self):
        """Test: Over-budget trip triggers Budget Agent rejection → revision → approval."""
        print_step(0, "Starting Negotiation - Over-Budget Paris Trip (Will Revise)")
        
        # User goal: over-budget trip
        user_goal = {
            "destination": "Paris",
            "budget": 1100,  # ~$157/day budget - enough for budget tier, not luxury
            "length_days": 7,
            "interests": ["cultural", "food"],
            "budget_tier": "luxury",  # Oops, chose luxury with moderate budget
            "passport_valid_months": 12,
        }
        print_step(1, "User Submits OVER-BUDGET Request", user_goal)
        
        # Round 1: Itinerary proposes luxury Paris
        itinerary_agent = MockItineraryAgent()
        itin_proposal_r1 = itinerary_agent.propose(user_goal, round_num=1)
        print_step(2, "Round 1: Itinerary Agent Proposes (Luxury)", itin_proposal_r1["proposal"])
        
        # Budget Agent REJECTS
        budget_agent = MockBudgetAgent()
        budget_verdict_r1 = budget_agent.review(itin_proposal_r1["proposal"], user_goal)
        print_step(3, "Round 1: Budget Agent REJECTS", budget_verdict_r1["proposal"])
        
        assert budget_verdict_r1["proposal"]["status"] == "rejected"
        assert "objection" in budget_verdict_r1["proposal"]
        print(f">> Objection: {budget_verdict_r1['proposal']['objection']}")
        
        # Round 2: Itinerary revises based on Budget objection
        objections_r1 = [
            {"agent": "budget", "reason": "over-budget"}
        ]
        itin_proposal_r2 = itinerary_agent.propose(user_goal, round_num=2, objections=objections_r1)
        print_step(4, "Round 2: Itinerary Agent Revises (Budget Tier)", itin_proposal_r2["proposal"])
        
        # Budget Agent APPROVES revised
        budget_verdict_r2 = budget_agent.review(itin_proposal_r2["proposal"], user_goal)
        print_step(5, "Round 2: Budget Agent APPROVES Revised", budget_verdict_r2["proposal"])
        
        assert budget_verdict_r2["proposal"]["status"] == "approved"
        
        # Logistics & Booking also check
        logistics_agent = MockLogisticsAgent()
        logistics_verdict = logistics_agent.review(itin_proposal_r2["proposal"])
        print_step(5.5, "Round 2: Logistics Agent Approves", logistics_verdict["proposal"])
        
        booking_agent = MockBookingAgent()
        booking_verdict = booking_agent.review(itin_proposal_r2["proposal"], user_goal)
        print_step(5.75, "Round 2: Booking Agent Approves", booking_verdict["proposal"])
        
        # Supervisor checks convergence on round 2
        supervisor = SupervisorAgent()
        all_verdicts = [budget_verdict_r2, logistics_verdict, booking_verdict]
        all_approved, objections = supervisor.check_convergence(all_verdicts)
        
        print_step(6, f"Round 2: Convergence Check", {
            "all_approved": all_approved,
            "objections": len(objections),
        })
        
        assert all_approved, "Should converge after Budget Agent gets revision"
        
        # Finalize
        final = supervisor.finalize("trip-456", itin_proposal_r2["proposal"], all_verdicts)
        print_step(7, "FINALIZED After 2 Rounds", {
            "destination": final["final_itinerary"]["destination"],
            "tier_used": final["final_itinerary"]["tier"],
            "status": final["status"],
        })
        
        assert final["status"] == "finalized"


def run_demo():
    """Run as standalone demo (not pytest)."""
    print("\n" + "="*70)
    print("TRIPNEGOTIATOR - LOCAL TESTING DEMO")
    print("="*70)
    
    test = TestMultiAgentNegotiation()
    
    print("\n\n" + "#"*70)
    print("# TEST 1: Successful Negotiation (Round 1)")
    print("#"*70)
    test.test_successful_negotiation_round_1()
    
    print("\n\n" + "#"*70)
    print("# TEST 2: Multi-Round Negotiation with Revision")
    print("#"*70)
    test.test_multi_round_negotiation_with_budget_rejection()
    
    print("\n\n" + "="*70)
    print("[SUCCESS] ALL LOCAL TESTS PASSED!")
    print("="*70)
    print("\nNext Steps:")
    print("  1. Implement actual Lambda agents with Groq")
    print("  2. Deploy to AWS using Terraform")
    print("  3. Run end-to-end test on AWS infrastructure")


if __name__ == "__main__":
    run_demo()
