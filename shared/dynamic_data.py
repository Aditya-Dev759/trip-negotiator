import json
from shared.web_search import web_search, web_search_with_sources, web_search_images, search_ddgs_news
from shared.s3_utils import load_destinations, load_cost_baselines, load_visa_rules, load_seasonal_notes
from shared.logging_utils import get_logger

log = get_logger("dynamic_data")


def _dedupe_sources(sources: list, limit: int = 5) -> list:
    """Dedupe a list of {"text"/"title", "url", ...} dicts down to
    [{"title", "url"}], dropping entries with no URL (nothing to cite) and
    capping the count so prompts/UI don't get flooded with links.
    """
    seen = set()
    deduped = []
    for s in sources:
        url = (s.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = (s.get("title") or "").strip() or url
        deduped.append({"title": title, "url": url})
        if len(deduped) >= limit:
            break
    return deduped


def get_destination_info(destination: str, interests: list = None) -> tuple:
    """Search for tourist spots and highlights for a destination based on interests.

    Returns (text_for_prompt, sources) where sources is a deduped list of
    {"title", "url"} the info was actually drawn from.
    """
    query = f"top attractions things to do in {destination}"
    if interests:
        query += " for " + ", ".join(interests)
    structured = web_search_with_sources(query, num_results=5)

    if not structured:
        log.info("[destination_info] live search empty, trying static fallback for %r", destination)
        try:
            static_data = load_destinations().get("destinations", [])
            for dest in static_data:
                if destination.lower() in dest.get("name", "").lower():
                    log.info("[destination_info] using STATIC reference data for %r", destination)
                    return (f"Static Reference: {dest.get('description', '')}. Avg daily cost: ${dest.get('avgDaily', 150)}", [])
        except Exception as e:
            log.warning("[destination_info] static fallback lookup failed: %s", e)
        log.info("[destination_info] no static match either, using generic placeholder text for %r", destination)
        return (f"Attractions and sightseeing highlights for {destination}.", [])

    log.info("[destination_info] using LIVE search results for %r", destination)
    text = "\n".join([f"- {s['text']}" for s in structured])
    return (text, _dedupe_sources(structured))


def get_interest_highlights(destination: str, interests: list) -> tuple:
    """Search for highlights specific to EACH of the traveler's selected
    interests (beach, cultural, food, shopping, nightlife, adventure,
    nature, museums, etc.) individually, rather than one generic
    "top attractions" query. This is what lets the itinerary agent build a
    plan that's genuinely tailored to what the traveler actually asked for,
    instead of a generic city overview that happens to mention their
    interests in passing.

    Returns (text_for_prompt, sources) -- text is organized one section per
    interest so the model can clearly map recommendations back to what the
    user selected.
    """
    if not interests:
        return ("No specific interests provided; use general highlights only.", [])

    sections = []
    all_sources = []
    for interest in interests:
        query = f"best {interest} experiences things to do in {destination}"
        structured = web_search_with_sources(query, num_results=3)
        if structured:
            snippet_lines = "\n".join([f"  - {s['text']}" for s in structured])
            sections.append(f"{interest.title()}:\n{snippet_lines}")
            all_sources.extend(structured)
        else:
            sections.append(f"{interest.title()}: no specific live results found; use general knowledge for this interest.")

    log.info("[interest_highlights] fetched live per-interest highlights for %r across %d interests", destination, len(interests))
    return ("\n\n".join(sections), _dedupe_sources(all_sources))


def get_destination_guide(destination: str) -> tuple:
    """Search for the practical "destination guide" details that make a trip
    summary genuinely useful beyond a bare day-by-day plan: the best time of
    year to visit (weather/crowds/cost tradeoffs), practical essentials
    (local language, currency, timezone), local culture/etiquette norms, and
    general safety/health notes for tourists.

    Each topic is a separate targeted search (mirrors get_interest_highlights)
    so the itinerary agent gets concrete, sourced information to weave into
    the trip summary as natural prose, rather than inventing generic filler.

    Returns (text_for_prompt, sources).
    """
    topics = [
        ("Best Time to Visit", f"best time of year to visit {destination} weather crowds cost"),
        ("Practical Essentials", f"{destination} local currency language timezone travel tips"),
        ("Culture & Etiquette", f"{destination} local customs etiquette tipping cultural tips for tourists"),
        ("Safety & Health", f"{destination} travel safety tips common scams health advice tourists"),
    ]

    sections = []
    all_sources = []
    for label, query in topics:
        structured = web_search_with_sources(query, num_results=3)
        if structured:
            snippet_lines = "\n".join([f"  - {s['text']}" for s in structured])
            sections.append(f"{label}:\n{snippet_lines}")
            all_sources.extend(structured)
        else:
            sections.append(f"{label}: no specific live results found; use general knowledge for this topic.")

    log.info("[destination_guide] fetched live guide info for %r across %d topics", destination, len(topics))
    return ("\n\n".join(sections), _dedupe_sources(all_sources, limit=8))


def get_destination_images(destination: str, num_images: int = 6) -> list:
    """Fetch a handful of representative photos for the destination.

    Best-effort only: returns [] if image search is unavailable or fails,
    never raises. Callers/UI must treat images as optional.
    """
    try:
        images = web_search_images(f"{destination} travel scenic photos", num_results=num_images)
        if images:
            log.info("[images] found %d image(s) for %r", len(images), destination)
        else:
            log.info("[images] no images found for %r", destination)
        return images
    except Exception as e:
        log.warning("[images] image lookup failed for %r: %s: %s", destination, type(e).__name__, e)
        return []


def get_weather_for_destination(destination: str) -> tuple:
    """Search for current/average weather information for a destination."""
    query = f"{destination} average monthly weather climate"
    structured = web_search_with_sources(query, num_results=3)

    if not structured:
        log.info("[weather] live search empty, trying static fallback for %r", destination)
        try:
            static_data = load_seasonal_notes().get("seasonalNotes", {})
            for key, val in static_data.items():
                if key in destination.lower() or destination.lower() in key:
                    log.info("[weather] using STATIC reference data for %r", destination)
                    return (f"Static Reference: {val.get('weatherWarnings', ['No alerts'])}", [])
        except Exception as e:
            log.warning("[weather] static fallback lookup failed: %s", e)
        log.info("[weather] no static match either, using generic placeholder text for %r", destination)
        return (f"Typical seasonal climate details for {destination}.", [])

    log.info("[weather] using LIVE search results for %r", destination)
    text = "\n".join([f"- {s['text']}" for s in structured])
    return (text, _dedupe_sources(structured))


def get_visa_requirements(destination: str) -> tuple:
    """Search for tourist visa requirements for citizens visiting the destination."""
    query = f"tourist visa entry requirements for {destination}"
    structured = web_search_with_sources(query, num_results=3)

    if not structured:
        log.info("[visa] live search empty, trying static fallback for %r", destination)
        try:
            static_data = load_visa_rules().get("visaRequirements", {})
            for key, val in static_data.items():
                if key in destination.lower() or destination.lower() in key:
                    log.info("[visa] using STATIC reference data for %r", destination)
                    return (f"Static Reference: Visa req is {val.get('usaCitizen', 'required/tourist card')}", [])
        except Exception as e:
            log.warning("[visa] static fallback lookup failed: %s", e)
        log.info("[visa] no static match either, using generic placeholder text for %r", destination)
        return (f"Visa rules and entry policies for {destination}.", [])

    log.info("[visa] using LIVE search results for %r", destination)
    text = "\n".join([f"- {s['text']}" for s in structured])
    return (text, _dedupe_sources(structured))


def get_travel_advisories(destination: str) -> tuple:
    """Search for current travel advisories, alerts, or closures for a destination.

    Prefers a DATED news search (past month) over a plain text search: a
    plain text search happily surfaces a years-old article about a
    long-resolved outbreak, a lifted travel ban, or a past weather event
    with nothing marking it as stale, and an LLM fed that has no way to
    tell it's not describing the present. If nothing recent turns up, this
    falls back to an undated text search but labels it explicitly as
    undated so the caller can tell the model to treat it with caution
    rather than presenting old information as a current warning.
    """
    query = f"travel advisory warnings safety updates {destination}"

    dated = search_ddgs_news(query, num_results=4, timelimit="m")
    if dated:
        log.info("[advisories] using LIVE dated news results for %r", destination)
        text = "\n".join([f"- {d['text']}" for d in dated])
        return (text, _dedupe_sources(dated))

    log.info("[advisories] no recent dated news found, trying undated text search for %r", destination)
    structured = web_search_with_sources(query, num_results=3)

    if not structured:
        log.info("[advisories] live search empty, no static source for this category, using generic text for %r", destination)
        return (f"No major warnings found for {destination}.", [])

    log.info("[advisories] using LIVE (undated) search results for %r", destination)
    text = (
        "UNDATED search results (publish date unknown -- these may describe a "
        "past, resolved situation; do not present as a current warning unless "
        "the text itself clearly indicates it is ongoing):\n"
        + "\n".join([f"- {s['text']}" for s in structured])
    )
    return (text, _dedupe_sources(structured))


def get_flight_cost_info(origin: str, destination: str) -> tuple:
    """Search for round-trip flight cost estimates between origin and destination.

    There's no static S3 fallback for this one (flight prices are far too
    route-specific and time-sensitive for any static reference file to be
    useful) -- if live search comes back empty we just tell the model that
    plainly so it estimates conservatively instead of inventing false
    precision.
    """
    if not origin:
        log.info("[flight_cost] no origin provided, skipping flight cost search for %r", destination)
        return ("No departure location provided; estimate flights using typical regional airfare.", [])

    query = f"average round trip flight price from {origin} to {destination}"
    structured = web_search_with_sources(query, num_results=4)

    if not structured:
        log.info("[flight_cost] live search empty, no static source for this category, using generic text for %r -> %r", origin, destination)
        return (f"No specific live flight pricing found for {origin} to {destination}; estimate using typical regional airfare for this route.", [])

    log.info("[flight_cost] using LIVE search results for %r -> %r", origin, destination)
    text = "\n".join([f"- {s['text']}" for s in structured])
    return (text, _dedupe_sources(structured))


def get_cost_info(destination: str, budget_tier: str) -> tuple:
    """Search for average accommodation, food, and transport costs for a destination and tier."""
    query = f"average daily travel cost in {destination} {budget_tier} budget hotels food"
    structured = web_search_with_sources(query, num_results=4)

    if not structured:
        log.info("[cost_info] live search empty, trying static fallback for %r (%s)", destination, budget_tier)
        try:
            static_data = load_cost_baselines().get("costBaselines", {})
            for key, val in static_data.items():
                if key in destination.lower() or destination.lower() in key:
                    log.info("[cost_info] using STATIC reference data for %r", destination)
                    return (f"Static Reference: Accommodation ({budget_tier}) is ${val.get('accommodation', {}).get(budget_tier, 50)}, food is ${val.get('food', {}).get(budget_tier, 20)}.", [])
        except Exception as e:
            log.warning("[cost_info] static fallback lookup failed: %s", e)
        log.info("[cost_info] no static match either, using generic placeholder text for %r", destination)
        return (f"Cost of lodging, dining, and transit in {destination}.", [])

    log.info("[cost_info] using LIVE search results for %r", destination)
    text = "\n".join([f"- {s['text']}" for s in structured])
    return (text, _dedupe_sources(structured))
