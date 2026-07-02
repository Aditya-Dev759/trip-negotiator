"""
In-memory, DynamoDB-shaped mock store for local development.

Mirrors the shared.dynamo_utils function signatures and return shapes
exactly, so every agent handler and api/main.py behave identically whether
they're talking to this in-memory store or the real DynamoDB table -- no
"local mode" branching needed anywhere else in the codebase.

Used by local_api_server.py, which calls install() to monkey-patch
shared.dynamo_utils BEFORE api.main (and the agent handlers it imports) are
loaded, since `from shared.dynamo_utils import X` binds a reference at
import time.
"""
from datetime import datetime
from typing import Any, Dict, List

from shared.logging_utils import get_logger

log = get_logger("local_mock_db")

# trip_id -> list of DynamoDB-item-shaped dicts (PK/SK/...), mirroring the
# single-table design in shared/dynamo_utils.py.
_ITEMS: Dict[str, List[Dict[str, Any]]] = {}


def create_trip_record(trip_id: str, user_id: str, goal: Dict) -> Dict:
    item = {
        "PK": f"TRIP#{trip_id}",
        "SK": "META",
        "userId": user_id,
        "goal": goal,
        "status": "initializing",
        "round": 0,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _ITEMS[trip_id] = [item]
    log.info("[local-db] created trip %s (destination=%r)", trip_id, goal.get("destination"))
    return item


def write_agent_proposal(trip_id: str, round_num: int, agent_name: str, proposal: Dict) -> None:
    if trip_id not in _ITEMS:
        log.warning("[local-db] write proposal failed: trip %s not found", trip_id)
        return
    item = {
        "PK": f"TRIP#{trip_id}",
        "SK": f"ROUND#{round_num}#AGENT#{agent_name}",
        "proposal": proposal,
        "status": proposal.get("status", "proposed"),
        "objection": proposal.get("objection"),
        "round": round_num,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _ITEMS[trip_id].append(item)
    log.debug("[local-db] recorded '%s' proposal for round %d (trip %s)", agent_name, round_num, trip_id)


def get_negotiation_history(trip_id: str) -> List[Dict]:
    return list(_ITEMS.get(trip_id, []))


def finalize_trip(trip_id: str, final_plan: Dict, unresolved_objections: List = None) -> None:
    if trip_id not in _ITEMS:
        return
    item = {
        "PK": f"TRIP#{trip_id}",
        "SK": "FINAL",
        "proposal": final_plan,
        "unresolved_objections": unresolved_objections or [],
        "status": "finalized",
        "timestamp": datetime.utcnow().isoformat(),
    }
    _ITEMS[trip_id].append(item)
    log.info("[local-db] finalized trip %s (%d unresolved objections)", trip_id, len(unresolved_objections or []))


def list_trips_for_user(user_id: str) -> List[Dict]:
    """Local stand-in for the real UserIdIndex GSI query -- just filters the
    in-memory META items by userId (there's effectively one demo user
    locally, so this always returns everything)."""
    results = []
    for items in _ITEMS.values():
        meta = next((i for i in items if i.get("SK") == "META"), None)
        if meta and meta.get("userId") == user_id:
            results.append(meta)
    return results


class _FakeTable:
    """Minimal stand-in for the boto3 DynamoDB Table resource -- only
    `update_item` is used outside the functions above (the supervisor
    handler calls it directly to flip the META record's status)."""

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None, ExpressionAttributeValues=None):
        pk = Key.get("PK", "")
        trip_id = pk.split("#")[-1] if "#" in pk else pk
        values = ExpressionAttributeValues or {}
        status = values.get(":status")
        round_val = values.get(":round")
        for item in _ITEMS.get(trip_id, []):
            if item.get("SK") == "META":
                if status:
                    item["status"] = status
                if round_val is not None:
                    item["round"] = round_val
        return {}


def get_table():
    return _FakeTable()


def install() -> None:
    """Monkey-patch shared.dynamo_utils to route through this in-memory
    store. Must be called before importing api.main or any agents.*.handler
    module."""
    import shared.dynamo_utils as dynamo_utils
    dynamo_utils.get_table = get_table
    dynamo_utils.create_trip_record = create_trip_record
    dynamo_utils.write_agent_proposal = write_agent_proposal
    dynamo_utils.finalize_trip = finalize_trip
    dynamo_utils.get_negotiation_history = get_negotiation_history
    dynamo_utils.list_trips_for_user = list_trips_for_user
    log.info("Local in-memory trip store installed (DynamoDB calls are mocked)")
