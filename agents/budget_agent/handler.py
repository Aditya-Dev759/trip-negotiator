import json
import sys
from pathlib import Path

# Add shared folder to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.groq_client import call_groq
from shared.dynamo_utils import write_agent_proposal
from shared.dynamic_data import get_cost_info, get_flight_cost_info
from shared.logging_utils import get_logger

log = get_logger("budget_agent")


def _fallback_cost_breakdown(user_budget: float, has_flights: bool) -> dict:
    """Naive proportional split used only if Groq is unreachable -- keeps the
    'where would my money go' summary populated even in fallback mode,
    rather than leaving the frontend with nothing to show.
    """
    if has_flights:
        weights = {"flights": 0.30, "accommodation": 0.35, "food": 0.20, "activities": 0.10, "local_transport": 0.05}
    else:
        # Domestic/no-flight trips: redistribute the flight share into lodging/activities.
        weights = {"flights": 0.0, "accommodation": 0.45, "food": 0.30, "activities": 0.15, "local_transport": 0.10}
    return {k: round(user_budget * w, 2) for k, w in weights.items()}


def _dedupe_sources(sources: list, limit: int = 6) -> list:
    seen = set()
    deduped = []
    for s in sources:
        url = (s.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append({"title": s.get("title") or url, "url": url})
        if len(deduped) >= limit:
            break
    return deduped


def lambda_handler(event, context):
    """
    Budget Agent: Validates itinerary against user's budget using live cost data from web search,
    and produces a category-by-category cost breakdown so the traveler can see where their money goes.
    """
    trip_id = event.get("trip_id")
    round_num = event.get("round", 1)
    goal = event.get("goal", {})
    itinerary = event.get("itinerary", {})

    origin = goal.get("origin", "")
    destination = goal.get("destination", "")
    user_budget = goal.get("budget", 1000)
    budget_tier = goal.get("budget_tier", "midrange")
    trip_length = goal.get("length_days", 7)

    log.info(
        "=== BudgetAgent | trip=%s round=%d | origin=%r destination=%r budget=%s tier=%s ===",
        trip_id, round_num, origin, destination, user_budget, budget_tier,
    )

    # 1. Fetch live cost estimates from web search (lodging/food/transit, plus
    #    a flight-cost lookup grounded in the traveler's stated origin).
    cost_info, cost_sources = get_cost_info(destination, budget_tier)
    flight_cost_info, flight_sources = get_flight_cost_info(origin, destination)
    sources = _dedupe_sources(cost_sources + flight_sources)

    # 2. Query Groq to review feasibility and produce a cost breakdown
    system_prompt = (
        "You are a strict financial auditor for travel plans.\n"
        "Your responses MUST be valid JSON conforming exactly to this structure:\n"
        "{\n"
        '  "status": "approved" | "rejected",\n'
        '  "estimated_cost": 1250.0,\n'
        '  "user_budget": 1000.0,\n'
        '  "cost_breakdown": {\n'
        '    "flights": 300.0,\n'
        '    "accommodation": 500.0,\n'
        '    "food": 250.0,\n'
        '    "activities": 150.0,\n'
        '    "local_transport": 50.0\n'
        "  },\n"
        '  "objection": "detailed reasoning of why it fails and concrete changes needed, or null if approved"\n'
        "}\n"
        "Rules:\n"
        "- If estimated cost is within 10% tolerance of the user's budget (estimated_cost <= user_budget * 1.1), approve it.\n"
        "- Otherwise, reject it and explain exactly which items are too expensive, and suggest adjustments (e.g. fewer days, lower lodging tier, cheaper activities).\n"
        "- cost_breakdown values MUST sum to approximately estimated_cost (within a few percent). Use the live flight pricing info given below to ground the 'flights' figure -- if no departure location was provided, set flights to 0 and fold that budget share into accommodation/activities instead.\n"
        "- Return ONLY the JSON object."
    )

    origin_line = f"Departing From: {origin}\n" if origin else "Departing From: not specified (treat as domestic/no-flight trip; flights should be 0)\n"

    user_prompt = (
        f"Review the following proposed itinerary for {destination}.\n"
        f"{origin_line}"
        f"Trip Length: {trip_length} days\n"
        f"User Total Budget: ${user_budget} (approx ${int(user_budget/trip_length)}/day)\n"
        f"Requested Tier: {budget_tier}\n\n"
        f"Itinerary summary: {itinerary.get('summary', '')}\n"
        f"Itinerary day-by-day activities:\n" + \
        "\n".join([f"Day {d.get('day')}: {', '.join(d.get('activities', []))}" for d in itinerary.get("days", [])]) + "\n\n"
        f"Live cost baseline information from web search:\n{cost_info}\n\n"
        f"Live flight pricing information from web search:\n{flight_cost_info}"
    )

    try:
        verdict = call_groq(user_prompt, system_prompt)
        if not verdict.get("cost_breakdown"):
            log.warning("BudgetAgent: Groq verdict missing cost_breakdown, filling with proportional fallback")
            verdict["cost_breakdown"] = _fallback_cost_breakdown(user_budget, bool(origin))
        log.info("BudgetAgent: using LIVE Groq verdict (round %d) -> status=%s", round_num, verdict.get("status"))
    except Exception as e:
        log.warning("BudgetAgent: FALLBACK verdict used -- Groq invocation failed: %s: %s", type(e).__name__, e)
        # Fallback verdict
        verdict = {
            "status": "approved",
            "estimated_cost": user_budget,
            "user_budget": user_budget,
            "cost_breakdown": _fallback_cost_breakdown(user_budget, bool(origin)),
            "objection": None
        }

    verdict["sources"] = sources

    # 3. Save verdict to DynamoDB
    write_agent_proposal(trip_id, round_num, "budget", verdict)

    # 4. Return state payload with budget verdict
    event["budget_verdict"] = verdict
    return event
