import json
import sys
from pathlib import Path

# Add shared folder to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.groq_client import call_groq
from shared.dynamo_utils import write_agent_proposal
from shared.dynamic_data import (
    get_destination_info,
    get_weather_for_destination,
    get_interest_highlights,
    get_destination_images,
    get_destination_guide,
)
from shared.logging_utils import get_logger

log = get_logger("itinerary_agent")


def _dedupe_sources(sources: list, limit: int = 10) -> list:
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


def _age_guidance(age: int) -> str:
    """Light-touch pacing/intensity guidance by age band. Deliberately does
    NOT override the traveler's explicitly selected interests (if a 65-year
    old selects "nightlife", that's still a real, explicit request) -- this
    only shapes pace, alcohol-related content, and physical intensity.
    """
    if age < 13:
        return (
            f"Traveler Age: {age} (child). Keep activities family-friendly and engaging for a child, "
            "avoid alcohol-centric venues entirely, keep days shorter with built-in downtime, and favor "
            "interactive/hands-on experiences over passive ones."
        )
    if age < 18:
        return (
            f"Traveler Age: {age} (teen). Keep activities age-appropriate -- no alcohol-centric nightlife "
            "content -- but the traveler can otherwise handle a fuller, more adventurous pace than a young child."
        )
    if age < 26:
        return (
            f"Traveler Age: {age} (young adult). Full pace and intensity are fine, including nightlife/"
            "adventure activities if selected as interests."
        )
    if age < 60:
        return (
            f"Traveler Age: {age} (adult). Standard pacing; balance activity-packed days with reasonable "
            "downtime."
        )
    return (
        f"Traveler Age: {age} (senior). Favor a more relaxed pace with fewer back-to-back high-exertion "
        "activities per day, more comfortable transport/seating options where relevant, and avoid scheduling "
        "very late-night activities unless the traveler explicitly selected nightlife as an interest."
    )


def lambda_handler(event, context):
    """
    Itinerary Agent: Proposes day-by-day itineraries based on user preferences and live web search.

    Also fetches per-interest highlights (one live search per selected
    interest category), a "destination guide" (best time of year to visit,
    practical essentials, culture/etiquette, safety) that gets woven into the
    prose summary rather than bolted on as a separate section, and a handful
    of destination photos -- so the final proposal carries a plan tailored to
    exactly what the traveler selected, genuinely useful travel-planning
    context, and the sources/images to back it all up.
    """
    trip_id = event.get("trip_id")
    goal = event.get("goal", {})

    destination = goal.get("destination", "")
    interests = goal.get("interests", [])
    trip_length = goal.get("length_days", 7)
    budget_tier = goal.get("budget_tier", "midrange")
    age = goal.get("age", 30)

    # 1. Determine if this is a revision loop
    round_num = event.get("round", 1)
    is_revision = "itinerary" in event

    objections = []
    if is_revision:
        round_num = round_num + 1
        # Extract objections from previous verdicts
        for agent_key in ["budget_verdict", "logistics_verdict", "booking_verdict"]:
            verdict = event.get(agent_key, {})
            if verdict.get("status") == "rejected" and verdict.get("objection"):
                objections.append({
                    "agent": agent_key.replace("_verdict", ""),
                    "objection": verdict.get("objection")
                })

    log.info(
        "=== ItineraryAgent | trip=%s round=%d | destination=%r tier=%s days=%d age=%s revision=%s objections=%d interests=%s ===",
        trip_id, round_num, destination, budget_tier, trip_length, age, is_revision, len(objections), interests,
    )

    # 2. Fetch live details via web search: general destination info, weather,
    #    a dedicated per-interest highlights search (one query per selected
    #    interest so each is genuinely represented, not just mentioned in
    #    passing), the practical "destination guide" (best time of year,
    #    essentials, etiquette, safety), and a handful of representative
    #    photos.
    dest_info, dest_sources = get_destination_info(destination, interests)
    weather, weather_sources = get_weather_for_destination(destination)
    interest_highlights, interest_sources = get_interest_highlights(destination, interests)
    guide_info, guide_sources = get_destination_guide(destination)
    images = get_destination_images(destination)

    all_sources = _dedupe_sources(
        dest_sources + weather_sources + interest_sources + guide_sources, limit=10
    )

    # 3. Create prompts for Groq LLM
    system_prompt = (
        "You are an expert travel planner creating personalized, day-by-day itineraries.\n"
        "Your responses MUST be valid JSON conforming exactly to this structure:\n"
        "{\n"
        '  "destination": "string",\n'
        '  "summary": "string",\n'
        '  "days": [\n'
        "    {\n"
        '      "day": 1,\n'
        '      "activities": ["activity 1", "activity 2"],\n'
        '      "meals": "breakfast/lunch/dinner description"\n'
        "    }\n"
        "  ],\n"
        '  "tier": "string",\n'
        '  "revision_note": "string or null"\n'
        "}\n"
        "Ensure the activities match the user's budget tier: " + budget_tier + ".\n"
        "This should be the BEST POSSIBLE plan for exactly what the traveler asked for: use the "
        "per-interest highlights provided below to make sure EVERY one of the traveler's selected "
        "interests is meaningfully represented somewhere across the itinerary, with specific, "
        "concrete activities drawn from those highlights rather than generic filler. Distribute "
        "interests sensibly across days rather than clustering them all on day 1.\n"
        "Also tailor pacing, intensity, and content appropriateness to the traveler's age (given below) -- "
        "this affects HOW activities are scheduled and described, not whether their selected interests are honored.\n"
        "The 'summary' field is not just a one-line blurb -- write it as a short, genuinely useful travel "
        "briefing (roughly 5-8 sentences of flowing prose, NOT a bulleted list) that weaves in, using the "
        "'Destination Guide' research provided below:\n"
        "  1) Best time of year to visit this destination (weather, crowds, cost tradeoffs) and, if the "
        "     traveler's trip doesn't fall in that ideal window, a brief honest note about what to expect "
        "     instead -- do not claim their trip dates are ideal if the research doesn't support that.\n"
        "  2) Practical essentials: local language, currency, and timezone.\n"
        "  3) One or two genuinely useful culture/etiquette tips for tourists.\n"
        "  4) Any real safety or health notes worth knowing, stated plainly without being alarmist -- if "
        "     research turns up nothing notable, it's fine to simply say the destination has no unusual "
        "     safety concerns for tourists rather than inventing a warning.\n"
        "Ground all of this in the research provided rather than generic travel-blog platitudes, and write "
        "it so it reads as one cohesive, welcoming briefing rather than a list of disconnected facts.\n"
        "Do not include markdown tags like ```json or other text. Return ONLY the JSON object."
    )

    age_guidance = _age_guidance(age)

    objections_text = ""
    if objections:
        objections_text = "\n\nCRITICAL: Address these previous objections in this revised itinerary:\n" + \
                          "\n".join([f"- {obj['agent']}: {obj['objection']}" for obj in objections])

    user_prompt = (
        f"Create a {trip_length}-day itinerary for {destination}.\n"
        f"Budget Tier: {budget_tier}\n"
        f"{age_guidance}\n"
        f"User Interests: {', '.join(interests) if interests else 'none specified -- use general highlights'}\n\n"
        f"Live Destination Info from Web Search:\n{dest_info}\n\n"
        f"Live Weather Info from Web Search:\n{weather}\n\n"
        f"Live Per-Interest Highlights from Web Search (weave these into the plan so each interest is genuinely represented):\n{interest_highlights}\n\n"
        f"Live Destination Guide Research from Web Search (weave this into the 'summary' field per the instructions above -- "
        f"best time to visit, practical essentials, culture/etiquette, safety):\n{guide_info}\n"
        f"{objections_text}"
    )

    try:
        proposal = call_groq(user_prompt, system_prompt)
        log.info("ItineraryAgent: using LIVE Groq-generated itinerary (round %d)", round_num)
    except Exception as e:
        log.warning("ItineraryAgent: FALLBACK plan used -- Groq invocation failed: %s: %s", type(e).__name__, e)
        # Fallback itinerary structure
        proposal = {
            "destination": destination,
            "summary": f"Exploring {destination} for {trip_length} days.",
            "days": [
                {
                    "day": i + 1,
                    "activities": [f"Visit popular local attractions in {destination} related to {', '.join(interests[:2]) if interests else 'sightseeing'}."],
                    "meals": "Enjoy local cafes and restaurants"
                }
                for i in range(trip_length)
            ],
            "tier": budget_tier,
            "revision_note": f"Fallback generated due to error: {str(e)}"
        }

    proposal["round"] = round_num
    # Sources/images are fetched independently of Groq, so attach them even
    # in fallback mode -- the traveler still gets citations and photos.
    proposal["sources"] = all_sources
    proposal["images"] = images

    # 4. Save proposal to DynamoDB
    write_agent_proposal(trip_id, round_num, "itinerary", proposal)

    # 5. Return updated state to Step Functions (clear old verdicts!)
    return {
        "trip_id": trip_id,
        "round": round_num,
        "goal": goal,
        "itinerary": proposal
    }
