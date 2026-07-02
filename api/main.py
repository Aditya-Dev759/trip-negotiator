"""
TripNegotiator API -- FastAPI app.

This module is intentionally deployment-agnostic: it only ever talks to
shared.dynamo_utils, never to an in-memory store directly. That means the
exact same code path runs in two situations:

  1. Local dev: local_api_server.py monkey-patches shared.dynamo_utils to an
     in-memory store (shared/local_mock_db.py) *before* importing this
     module, then boots it with uvicorn. Interactive docs at /docs.

  2. Real AWS: this module is the actual Lambda entry point behind API
     Gateway. infra/lambda.tf builds a container image (Dockerfile.lambda)
     and deploys it as aws_lambda_function.api with
     image_config.command = ["api.main.handler"] -- the `handler` object at
     the bottom of this file (a Mangum-wrapped ASGI app) is exactly what
     that points at. shared.dynamo_utils then talks to the real DynamoDB
     table, and STATE_MACHINE_ARN (set by lambda.tf) routes trip creation
     through Step Functions instead of the in-process negotiation loop.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shared.logging_utils import configure_logging, get_logger

configure_logging()
log = get_logger("api")

from shared.dynamo_utils import create_trip_record, get_negotiation_history, list_trips_for_user
from shared.ssl_utils import get_ssl_context
from shared.currency_utils import get_exchange_rate_for_countries

# These imports must happen AFTER any shared.dynamo_utils monkey-patching
# has already run (see local_api_server.py) -- each agents/*/handler.py does
# `from shared.dynamo_utils import write_agent_proposal` at import time,
# which binds whatever function is currently installed there.
from agents.itinerary_agent.handler import lambda_handler as itinerary_handler
from agents.budget_agent.handler import lambda_handler as budget_handler
from agents.logistics_agent.handler import lambda_handler as logistics_handler
from agents.booking_agent.handler import lambda_handler as booking_handler
from agents.supervisor.handler import lambda_handler as supervisor_handler

MAX_ROUNDS = 3
DEMO_USER_ID = "user-123"  # stand-in until Cognito auth is wired up

# Open-Meteo's geocoding API (https://open-meteo.com/en/docs/geocoding-api)
# is free, open, and keyless -- same bar as ddgs/Frankfurter elsewhere in
# this app. Used to power the location-picker autocomplete on the frontend
# instead of the user free-typing a destination/origin string.
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

app = FastAPI(
    title="TripNegotiator API",
    description="Multi-agent trip negotiation backend. Try requests interactively below.",
    version="1.0.0",
)

# In AWS, infra/lambda.tf sets ALLOWED_ORIGINS to the real CloudFront domain
# (plus localhost for convenience) so this doesn't wildcard-allow every
# origin in production. Locally (no env var set) it falls back to "*" since
# local dev has no fixed frontend origin to pin to and nothing sensitive is
# exposed on localhost.
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
_allowed_origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TripGoal(BaseModel):
    # Where the traveler is departing from -- used to ground flight-cost
    # estimates (BudgetAgent) and the cost breakdown shown to the user.
    origin: str
    destination: str
    # ISO 3166-1 alpha-2 country codes, populated when the traveler selects
    # a suggestion from the /locations/search-backed autocomplete on the
    # frontend (rather than free-typing). Optional because older clients /
    # manual API calls may not supply them -- in that case the exchange
    # rate widget just won't have anything to look up.
    origin_country_code: Optional[str] = None
    destination_country_code: Optional[str] = None
    budget: float = Field(gt=0)
    length_days: int = Field(gt=0, le=60)
    interests: List[str] = []
    budget_tier: Literal["budget", "midrange", "luxury"] = "midrange"
    passport_required: bool = True
    passport_valid_months: int = 12
    # Traveler's age -- used by the itinerary agent to tailor the pace and
    # nature of recommended activities (e.g. nightlife-heavy vs.
    # family/senior-friendly pacing).
    age: int = Field(gt=0, le=120, default=30)


class TripCreateRequest(BaseModel):
    goal: TripGoal


class TripCreateResponse(BaseModel):
    trip_id: str
    status: str
    message: str


def run_negotiation_workflow(trip_id: str, goal: dict) -> None:
    """Runs the bounded multi-agent negotiation loop in-process.

    This is the local-dev / no-Step-Functions stand-in for the real
    architecture (see infra/statemachine.asl.json): each agent still runs as
    its own Lambda-shaped handler function, we're just calling them directly
    in sequence here instead of via a state machine.
    """
    try:
        event = {"trip_id": trip_id, "round": 1, "goal": goal, "allApproved": False}
        workflow_start = time.monotonic()

        while event["round"] <= MAX_ROUNDS:
            current_round = event["round"]
            round_start = time.monotonic()
            log.info("########## Trip %s | Round %d starting ##########", trip_id, current_round)

            event = itinerary_handler(event, None)
            event = budget_handler(event, None)
            event = logistics_handler(event, None)
            event = booking_handler(event, None)

            all_approved = event.get("allApproved", False)
            round_elapsed = time.monotonic() - round_start
            log.info(
                "########## Trip %s | Round %d complete in %.2fs, all_approved=%s ##########",
                trip_id, current_round, round_elapsed, all_approved,
            )

            if all_approved:
                log.info("Trip %s: negotiation converged on round %d", trip_id, current_round)
                break

            if current_round < MAX_ROUNDS:
                log.info("Trip %s: objections found, moving to round %d", trip_id, current_round + 1)
                event["round"] = current_round + 1
                event["allApproved"] = False
                time.sleep(1.0)
            else:
                log.info("Trip %s: reached max round limit (%d), force-finalizing", trip_id, MAX_ROUNDS)
                break

        supervisor_handler(event, None)
        total_elapsed = time.monotonic() - workflow_start
        log.info("Trip %s: negotiation workflow finished in %.2fs total", trip_id, total_elapsed)

    except Exception as e:
        log.error("Trip %s: negotiation workflow crashed: %s: %s", trip_id, type(e).__name__, e)


def _build_trip_details(trip_id: str) -> Optional[Dict[str, Any]]:
    """Reassembles a trip's full state from its DynamoDB-shaped item history."""
    items = get_negotiation_history(trip_id)
    if not items:
        return None

    meta_item = next((item for item in items if item["SK"] == "META"), None)
    final_item = next((item for item in items if item["SK"] == "FINAL"), None)
    if not meta_item:
        return None

    rounds_dict: Dict[int, Dict[str, Any]] = {}
    for item in items:
        sk = item["SK"]
        if sk.startswith("ROUND#"):
            parts = sk.split("#")
            round_num = int(parts[1])
            agent_name = parts[3]

            if round_num not in rounds_dict:
                rounds_dict[round_num] = {
                    "round": round_num,
                    "itinerary": None,
                    "budget_verdict": None,
                    "logistics_verdict": None,
                    "booking_verdict": None,
                    "all_approved": False,
                }

            proposal = item.get("proposal", {})
            if agent_name in ("itinerary_agent", "itinerary"):
                rounds_dict[round_num]["itinerary"] = proposal
            elif agent_name in ("budget_agent", "budget"):
                rounds_dict[round_num]["budget_verdict"] = proposal
            elif agent_name in ("logistics_agent", "logistics"):
                rounds_dict[round_num]["logistics_verdict"] = proposal
            elif agent_name in ("booking_agent", "booking"):
                rounds_dict[round_num]["booking_verdict"] = proposal

    for r_data in rounds_dict.values():
        itin = r_data["itinerary"]
        b_ver = r_data["budget_verdict"]
        l_ver = r_data["logistics_verdict"]
        bk_ver = r_data["booking_verdict"]
        if itin and b_ver and l_ver and bk_ver:
            r_data["all_approved"] = (
                b_ver.get("status") == "approved"
                and l_ver.get("status") == "approved"
                and bk_ver.get("status") == "approved"
            )

    rounds_list = sorted(rounds_dict.values(), key=lambda x: x["round"])

    status = final_item.get("status", "in_progress") if final_item else meta_item.get("status", "initializing")
    if not final_item and rounds_list:
        status = "negotiating"

    # NOTE: the frontend expects final_plan to be an envelope wrapping the
    # itinerary under `final_itinerary` (matching what supervisor/handler.py
    # writes and what NegotiationProgress.tsx reads via
    # `trip.final_plan?.final_itinerary`) -- NOT the itinerary object itself.
    final_plan = None
    if final_item:
        final_plan = {
            "trip_id": trip_id,
            "status": "finalized",
            "final_itinerary": final_item.get("proposal"),
            "unresolved_objections": final_item.get("unresolved_objections", []),
        }

    return {
        "trip_id": trip_id,
        "goal": meta_item.get("goal"),
        "status": status,
        "rounds": rounds_list,
        "final_plan": final_plan,
        "created_at": meta_item.get("timestamp"),
        "updated_at": final_item.get("timestamp") if final_item else meta_item.get("timestamp"),
    }


@app.post("/trips", response_model=TripCreateResponse, status_code=201)
def create_trip(request: TripCreateRequest, background_tasks: BackgroundTasks):
    """Start a new trip negotiation."""
    goal = request.goal.model_dump()
    trip_id = str(uuid.uuid4())

    groq_key = os.environ.get("GROQ_API_KEY") or os.environ.get("SSM_GROQ_KEY_PARAM", "")
    if not groq_key:
        log.warning("No Groq API key found in environment -- check your .env file")

    create_trip_record(trip_id, DEMO_USER_ID, goal)
    log.info("Created trip %s (origin=%r destination=%r age=%s)", trip_id, goal.get("origin"), goal.get("destination"), goal.get("age"))

    state_machine_arn = os.environ.get("STATE_MACHINE_ARN")
    if state_machine_arn:
        # Real deployment: hand off to Step Functions instead of running the
        # negotiation loop in this process.
        import boto3
        sfn = boto3.client("stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"trip-{trip_id}",
            input=json.dumps({"trip_id": trip_id, "round": 1, "goal": goal, "allApproved": False}),
        )
        log.info("Trip %s: started Step Functions execution", trip_id)
    else:
        # Local dev (or any environment without Step Functions wired up):
        # run the same negotiation loop as a FastAPI background task.
        background_tasks.add_task(run_negotiation_workflow, trip_id, goal)

    return TripCreateResponse(
        trip_id=trip_id, status="initializing", message="Negotiation workflow started successfully"
    )


@app.get("/trips")
def list_trips():
    """List trip summaries for the (currently single, demo) user."""
    meta_items = list_trips_for_user(DEMO_USER_ID)
    trips = []
    for item in meta_items:
        trip_id = item["PK"].split("#")[1]
        history = get_negotiation_history(trip_id)
        final_item = next((h for h in history if h["SK"] == "FINAL"), None)
        status = "finalized" if final_item else item.get("status", "initializing")
        trips.append({
            "trip_id": trip_id,
            "goal": item.get("goal"),
            "status": status,
            "created_at": item.get("timestamp"),
            "updated_at": final_item.get("timestamp") if final_item else item.get("timestamp"),
        })
    return sorted(trips, key=lambda x: x["created_at"], reverse=True)


@app.get("/trips/{trip_id}")
def get_trip(trip_id: str):
    """Get a trip's full negotiation history and current status."""
    details = _build_trip_details(trip_id)
    if details is None:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")
    return details


@app.get("/locations/search")
def search_locations(q: str = Query(..., min_length=1, description="Place name to search for")):
    """Proxy to Open-Meteo's free, keyless geocoding API, powering the
    frontend's location-picker autocomplete (destination/origin) instead of
    free-text entry. Returns a simplified list of candidate places with
    enough info (name, admin1/region, country, country_code) to disambiguate
    same-named places (e.g. there's a Kyoto in Japan AND in Tanzania).

    Never raises to the caller -- returns an empty list on any upstream
    failure so the frontend can fall back to plain text entry gracefully.
    """
    params = {"name": q, "count": 8, "language": "en", "format": "json"}
    url = GEOCODING_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=8, context=get_ssl_context()) as response:
            data = json.loads(response.read().decode("utf-8"))
            raw_results = data.get("results", []) or []
            results = [
                {
                    "name": r.get("name", ""),
                    "admin1": r.get("admin1", ""),
                    "country": r.get("country", ""),
                    "country_code": r.get("country_code", ""),
                    "latitude": r.get("latitude"),
                    "longitude": r.get("longitude"),
                }
                for r in raw_results
            ]
            log.info("Location search %r -> %d result(s)", q, len(results))
            return {"results": results}
    except Exception as e:
        log.warning("Location search failed for %r: %s: %s", q, type(e).__name__, e)
        return {"results": []}


@app.get("/exchange-rate")
def exchange_rate(
    from_country: str = Query(..., min_length=2, max_length=2, description="Origin ISO country code, e.g. CA"),
    to_country: str = Query(..., min_length=2, max_length=2, description="Destination ISO country code, e.g. JP"),
):
    """Latest exchange rate between the traveler's origin and destination
    countries, via the free/keyless Frankfurter API (ECB reference rates).
    Returns {"available": false} rather than an error if either country's
    currency can't be resolved or the live lookup fails -- the frontend
    treats this widget as optional, same as images/sources elsewhere.
    """
    result = get_exchange_rate_for_countries(from_country.upper(), to_country.upper())
    if result is None:
        return {"available": False}
    return {"available": True, **result}


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Lambda entrypoint ---------------------------------------------------
# Wrapping the FastAPI app with Mangum makes this module directly usable as
# an AWS Lambda handler behind API Gateway (HTTP API or REST API).
# infra/lambda.tf builds aws_lambda_function.api from Dockerfile.lambda with
# image_config.command = ["api.main.handler"] -- that's exactly this
# `handler` object. Locally this import is inert -- uvicorn drives `app`
# directly instead (see local_api_server.py).
from mangum import Mangum

handler = Mangum(app)
