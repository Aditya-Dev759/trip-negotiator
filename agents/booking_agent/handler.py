import json
import sys
from pathlib import Path

# Add shared folder to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.groq_client import call_groq
from shared.dynamo_utils import write_agent_proposal
from shared.dynamic_data import get_visa_requirements
from shared.logging_utils import get_logger

log = get_logger("booking_agent")


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
    Booking Agent: Checks visa rules, minimum passport validity, and general booking constraints.
    Calculates the final 'allApproved' parameter for Step Functions.
    """
    trip_id = event.get("trip_id")
    round_num = event.get("round", 1)
    goal = event.get("goal", {})
    itinerary = event.get("itinerary", {})

    destination = goal.get("destination", "")
    # Not every traveler needs a passport -- domestic trips, or trips to a
    # country the traveler is a citizen of, have no passport/visa requirement
    # at all. Default to True to preserve prior behavior for international
    # trips where this flag wasn't supplied.
    passport_required = goal.get("passport_required", True)
    passport_valid_months = goal.get("passport_valid_months", 6)

    log.info(
        "=== BookingAgent | trip=%s round=%d | destination=%r passport_required=%s passport_valid_months=%s ===",
        trip_id, round_num, destination, passport_required, passport_valid_months,
    )

    # 1. Fetch live visa details from web search (skip if no passport needed)
    if passport_required:
        visa_info, visa_sources = get_visa_requirements(destination)
    else:
        visa_info = "Not applicable: traveler does not need a passport for this trip (domestic travel or travel within their own country of citizenship)."
        visa_sources = []
    sources = _dedupe_sources(visa_sources)

    # 2. Query Groq to review booking and visa feasibility
    if passport_required:
        system_prompt = (
            "You are an expert booking and visa compliance officer.\n"
            "Your responses MUST be valid JSON conforming exactly to this structure:\n"
            "{\n"
            '  "status": "approved" | "rejected",\n'
            '  "visa_requirement": "summary of visa requirement for the traveler",\n'
            '  "objection": "reason for rejection and recommended adjustment, or null if approved"\n'
            "}\n"
            "Rules:\n"
            "- If passport validity is less than 6 months (passport_valid_months < 6), reject it immediately because most destinations require at least 6 months validity.\n"
            "- Review visa requirements for the destination. If there is a major issue or warning, highlight it.\n"
            "- Return ONLY the JSON object."
        )
        user_prompt = (
            f"Review the visa and entry compliance for traveling to {destination}.\n\n"
            f"User Passport Validity: {passport_valid_months} months remaining\n"
            f"Itinerary Destination: {destination}\n\n"
            f"Live entry visa requirement details from web search:\n{visa_info}"
        )
    else:
        system_prompt = (
            "You are an expert booking and travel compliance officer.\n"
            "Your responses MUST be valid JSON conforming exactly to this structure:\n"
            "{\n"
            '  "status": "approved" | "rejected",\n'
            '  "visa_requirement": "short note confirming no passport/visa is required",\n'
            '  "objection": "reason for rejection, or null if approved"\n'
            "}\n"
            "Rules:\n"
            "- The traveler does NOT need a passport for this trip (it is domestic travel, or they are a citizen of the destination country). Do NOT reject based on passport validity -- that rule does not apply here.\n"
            "- Only reject if there is some other genuine, serious entry/compliance blocker surfaced by the live info below.\n"
            "- Return ONLY the JSON object."
        )
        user_prompt = (
            f"Review booking/entry compliance for a trip to {destination}.\n\n"
            f"{visa_info}\n\n"
            f"Itinerary Destination: {destination}"
        )

    try:
        verdict = call_groq(user_prompt, system_prompt)
        log.info("BookingAgent: using LIVE Groq verdict (round %d) -> status=%s", round_num, verdict.get("status"))
    except Exception as e:
        log.warning("BookingAgent: FALLBACK verdict used -- Groq invocation failed: %s: %s", type(e).__name__, e)
        if passport_required:
            approved = passport_valid_months >= 6
            verdict = {
                "status": "approved" if approved else "rejected",
                "visa_requirement": "Standard travel policies apply.",
                "objection": None if approved else "Passport validity is less than 6 months, which is required for international travel."
            }
        else:
            verdict = {
                "status": "approved",
                "visa_requirement": "No passport required for this trip.",
                "objection": None
            }

    verdict["sources"] = sources

    # 3. Save verdict to DynamoDB
    write_agent_proposal(trip_id, round_num, "booking", verdict)

    # 4. Determine if ALL review agents approved in this round
    budget_verdict = event.get("budget_verdict", {})
    logistics_verdict = event.get("logistics_verdict", {})

    budget_approved = budget_verdict.get("status") == "approved"
    logistics_approved = logistics_verdict.get("status") == "approved"
    booking_approved = verdict.get("status") == "approved"

    all_approved = budget_approved and logistics_approved and booking_approved

    log.info(
        "=== Round %d verdict summary | trip=%s | budget=%s logistics=%s booking=%s -> all_approved=%s ===",
        round_num, trip_id,
        budget_verdict.get("status"), logistics_verdict.get("status"), verdict.get("status"),
        all_approved,
    )

    # 5. Return updated state payload with booking verdict and convergence status
    event["booking_verdict"] = verdict
    event["allApproved"] = all_approved

    return event
