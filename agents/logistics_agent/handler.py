import json
import sys
from datetime import date
from pathlib import Path

# Add shared folder to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.groq_client import call_groq
from shared.dynamo_utils import write_agent_proposal
from shared.dynamic_data import get_travel_advisories, get_weather_for_destination
from shared.logging_utils import get_logger

log = get_logger("logistics_agent")


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
    Logistics Agent: Checks travel-time feasibility, opening hours, weather warnings, and seasonal closures.
    """
    trip_id = event.get("trip_id")
    round_num = event.get("round", 1)
    goal = event.get("goal", {})
    itinerary = event.get("itinerary", {})

    destination = goal.get("destination", "")
    today = date.today().isoformat()

    log.info("=== LogisticsAgent | trip=%s round=%d | destination=%r today=%s ===", trip_id, round_num, destination, today)

    # 1. Fetch live travel alerts & climate constraints from web search
    advisories, advisory_sources = get_travel_advisories(destination)
    weather, weather_sources = get_weather_for_destination(destination)
    sources = _dedupe_sources(advisory_sources + weather_sources)

    # 2. Query Groq to review logistics
    system_prompt = (
        "You are an expert travel logistics auditor.\n"
        "Your responses MUST be valid JSON conforming exactly to this structure:\n"
        "{\n"
        '  "status": "approved" | "rejected",\n'
        '  "warnings": ["warning 1", "warning 2"],\n'
        '  "objection": "reason for rejection and recommended adjustment, or null if approved"\n'
        "}\n"
        "Rules:\n"
        "- Reject the itinerary if any planned activity is impossible due to seasonal closures, extreme weather, major safety closures, or is logistically unrealistic (e.g. traveling between distant cities on the same afternoon).\n"
        "- If there are only minor weather issues (e.g. hot season or rainy season warnings), approve but include warnings in the list.\n"
        "- IMPORTANT -- fact-check advisories against today's date before including them: advisory/news snippets below may be prefixed with a publish date like [YYYY-MM-DD], or marked UNDATED.\n"
        "  * Only surface a warning if it describes a situation that is still current/ongoing as of today. An outbreak, ban, closure, or unrest that was reported months or years ago and isn't clearly still active should NOT be presented as a live warning -- it may already be resolved.\n"
        "  * If a snippet is UNDATED, only use it if its own wording clearly signals it's an ongoing/current policy (e.g. standing visa rules) rather than a one-time news event -- otherwise disregard it.\n"
        "  * If every advisory snippet you were given is stale, resolved, or too uncertain to confirm as current, return an empty warnings list for advisories rather than repeating outdated information as if it's happening now. It is better to omit a warning than to falsely alarm the traveler about something that's no longer true.\n"
        "- Return ONLY the JSON object."
    )

    user_prompt = (
        f"Today's Date: {today}\n\n"
        f"Review the following proposed itinerary for {destination}.\n\n"
        f"Itinerary summary: {itinerary.get('summary', '')}\n"
        f"Itinerary day-by-day activities:\n" + \
        "\n".join([f"Day {d.get('day')}: {', '.join(d.get('activities', []))}" for d in itinerary.get("days", [])]) + "\n\n"
        f"Live climate/weather info from web search:\n{weather}\n\n"
        f"Live travel advisories/safety/closures from web search (check each snippet's date against today's date, {today}, before treating it as current):\n{advisories}"
    )

    try:
        verdict = call_groq(user_prompt, system_prompt)
        log.info("LogisticsAgent: using LIVE Groq verdict (round %d) -> status=%s", round_num, verdict.get("status"))
    except Exception as e:
        log.warning("LogisticsAgent: FALLBACK verdict used -- Groq invocation failed: %s: %s", type(e).__name__, e)
        verdict = {
            "status": "approved",
            "warnings": [f"Fallback mode: {str(e)}"],
            "objection": None
        }

    verdict["sources"] = sources

    # 3. Save verdict to DynamoDB
    write_agent_proposal(trip_id, round_num, "logistics", verdict)

    # 4. Return state payload with logistics verdict
    event["logistics_verdict"] = verdict
    return event
