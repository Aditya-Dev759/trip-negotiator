"""
Mock agent implementations for local testing.
Simulates the multi-agent negotiation flow without Groq calls.
"""

import json
from datetime import datetime
from typing import Dict, List, Tuple
from tests.local_test_utils import load_reference_data


class MockItineraryAgent:
    """Mock Itinerary Agent - proposes trip plans."""
    
    def propose(self, goal: Dict, round_num: int = 1, objections: List[Dict] = None) -> Dict:
        """
        Propose an itinerary based on goal and prior objections.
        
        Args:
            goal: User's trip goal (destination, budget, length, interests)
            round_num: Which negotiation round
            objections: Prior objections from other agents
            
        Returns:
            Proposed itinerary
        """
        destinations = load_reference_data("destinations.json")["destinations"]
        
        # Find destination matching interests
        matched_dest = None
        for dest in destinations:
            if goal["destination"].lower() in dest["name"].lower():
                matched_dest = dest
                break
        
        if not matched_dest:
            matched_dest = destinations[0]  # Default to Tokyo
        
        # Build itinerary
        itinerary = {
            "id": f"ITIN#{round_num}",
            "destination": matched_dest["name"],
            "country": matched_dest["country"],
            "length_days": goal.get("length_days", 7),
            "interests": goal.get("interests", []),
            "tier": goal.get("budget_tier", "midrange"),
            "daily_budget": goal.get("budget", 150) / goal.get("length_days", 7),
            "proposed_activities": [
                {"day": 1, "activity": "Arrival & settling in"},
                {"day": 2, "activity": "Cultural exploration"},
                {"day": 3, "activity": "Adventure & nature"},
                {"day": 4, "activity": "Food & nightlife"},
                {"day": 5, "activity": "Shopping & museums"},
                {"day": 6, "activity": "Relaxation & local experiences"},
                {"day": 7, "activity": "Departure"},
            ],
            "revision_note": None,
        }
        
        # Adjust if there were objections
        if objections and round_num > 1:
            for obj in objections:
                if obj["agent"] == "budget":
                    # Lower tier if budget objection
                    itinerary["tier"] = "budget"
                    itinerary["daily_budget"] *= 0.8
                    itinerary["revision_note"] = f"Revised to budget tier per round {round_num-1} feedback"
        
        return {
            "agent": "itinerary",
            "round": round_num,
            "status": "proposed",
            "proposal": itinerary,
            "timestamp": datetime.utcnow().isoformat(),
        }


class MockBudgetAgent:
    """Mock Budget Agent - validates budget feasibility."""
    
    def review(self, itinerary: Dict, goal: Dict) -> Dict:
        """
        Review itinerary against budget.
        
        Args:
            itinerary: Proposed itinerary from Itinerary Agent
            goal: User's original goal
            
        Returns:
            Approval or rejection with reasoning
        """
        cost_baselines = load_reference_data("cost_baselines.json")["costBaselines"]
        
        dest_name = itinerary["destination"].lower().replace(" ", "")
        
        # Find matching cost baseline
        costs = None
        for key in cost_baselines:
            if key in dest_name or dest_name in key:
                costs = cost_baselines[key]
                break
        
        if not costs:
            costs = cost_baselines.get("bali", {})  # Default cheap destination
        
        # Calculate estimated total cost
        tier = itinerary["tier"]
        days = itinerary["length_days"]
        
        daily_cost = (
            costs.get("accommodation", {}).get(tier, 50)
            + costs.get("food", {}).get(tier, 20)
            + costs.get("activities", {}).get(tier, 30)
            + costs.get("transport", {}).get(tier, 5)
        )
        
        estimated_total = daily_cost * days
        user_budget = goal.get("budget", 1000)
        
        approved = estimated_total <= user_budget * 1.1  # 10% tolerance
        
        verdict = {
            "agent": "budget",
            "status": "approved" if approved else "rejected",
            "estimated_cost": estimated_total,
            "user_budget": user_budget,
            "daily_breakdown": daily_cost,
        }
        
        if not approved:
            verdict["objection"] = (
                f"Estimated total cost ${estimated_total:.2f} exceeds budget ${user_budget}. "
                f"Suggest {tier} tier (${daily_cost}/day) or reduce trip length."
            )
        
        return {
            "agent": "budget",
            "round": (itinerary.get("revision_note") or "").count("round") + 1,
            "proposal": verdict,
            "timestamp": datetime.utcnow().isoformat(),
        }


class MockLogisticsAgent:
    """Mock Logistics Agent - validates travel logistics."""
    
    def review(self, itinerary: Dict) -> Dict:
        """
        Review itinerary for logistics feasibility.
        
        Args:
            itinerary: Proposed itinerary
            
        Returns:
            Approval or rejection with reasoning
        """
        seasonal = load_reference_data("seasonal_notes.json")["seasonalNotes"]
        dest_name = itinerary["destination"].lower().replace(" ", "")
        
        # Find matching seasonal data
        seasonal_data = seasonal.get("bali", {})
        
        warnings = []
        for key in seasonal:
            if key in dest_name or dest_name in key:
                seasonal_data = seasonal[key]
                break
        
        # Check for weather warnings
        if seasonal_data.get("weatherWarnings"):
            warnings.extend(seasonal_data["weatherWarnings"])
        
        # Check for closures (these DO cause rejection)
        closures = seasonal_data.get("closures", [])
        
        # Only reject if there are actual closures; warnings are just noted
        approved = len(closures) == 0
        
        verdict = {
            "agent": "logistics",
            "status": "approved" if approved else "rejected",
            "destination": itinerary["destination"],
            "warnings": warnings,
        }
        
        if not approved:
            verdict["objection"] = f"Logistic issues: {'; '.join(closures)}"
        
        return {
            "agent": "logistics",
            "round": 1,
            "proposal": verdict,
            "timestamp": datetime.utcnow().isoformat(),
        }


class MockBookingAgent:
    """Mock Booking Agent - validates booking constraints."""
    
    def review(self, itinerary: Dict, goal: Dict) -> Dict:
        """
        Review itinerary for booking constraints.
        
        Args:
            itinerary: Proposed itinerary
            goal: User's goal
            
        Returns:
            Approval or rejection with reasoning
        """
        visa_rules = load_reference_data("visa_rules.json")["visaRequirements"]
        
        country = itinerary["country"].lower()
        
        # Find visa requirement
        visa_req = visa_rules.get(country, {})
        
        has_valid_passport = goal.get("passport_valid_months", 6) >= 6
        
        approved = has_valid_passport
        
        verdict = {
            "agent": "booking",
            "status": "approved" if approved else "rejected",
            "destination": itinerary["destination"],
            "visa_requirement": visa_req.get("usaCitizen", "unknown"),
        }
        
        if not approved:
            verdict["objection"] = "Passport validity insufficient for travel"
        
        return {
            "agent": "booking",
            "round": 1,
            "proposal": verdict,
            "timestamp": datetime.utcnow().isoformat(),
        }


class SupervisorAgent:
    """Mock Supervisor - orchestrates negotiation and finalizes."""
    
    def check_convergence(self, verdicts: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Check if all agents have approved.
        
        Args:
            verdicts: List of agent verdicts
            
        Returns:
            (all_approved, list_of_objections)
        """
        all_approved = all(v.get("proposal", {}).get("status") == "approved" for v in verdicts)
        objections = [v for v in verdicts if v.get("proposal", {}).get("status") == "rejected"]
        
        return all_approved, objections
    
    def finalize(self, trip_id: str, itinerary: Dict, all_verdicts: List[Dict], unresolved: List[Dict] = None) -> Dict:
        """
        Finalize trip planning.
        
        Args:
            trip_id: Trip ID
            itinerary: Final itinerary
            all_verdicts: All agent verdicts
            unresolved: Unresolved objections (if force-finalized)
            
        Returns:
            Final trip plan
        """
        return {
            "trip_id": trip_id,
            "status": "finalized",
            "final_itinerary": itinerary,
            "all_verdicts": all_verdicts,
            "unresolved_objections": unresolved or [],
            "finalized_at": datetime.utcnow().isoformat(),
        }
