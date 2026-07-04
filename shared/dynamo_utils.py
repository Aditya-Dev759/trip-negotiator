import os
import json
import boto3
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any

_dynamodb = None


def _get_resource():
    """Lazily create the boto3 DynamoDB resource.

    This must NOT run at import time: local_api_server.py imports this module
    and then monkey-patches get_table()/create_trip_record()/etc. with in-memory
    mocks before ever calling them for real. If we constructed the boto3
    resource eagerly at module load, it would raise NoRegionError locally
    (no AWS_REGION set outside a Lambda runtime) before the mocks are ever
    applied, crashing the local server on startup.
    """
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _dynamodb


def get_table():
    """Get DynamoDB table reference."""
    return _get_resource().Table(os.environ.get("DYNAMODB_TABLE", "tripnegotiator-negotiations"))


def _floats_to_decimal(value: Any) -> Any:
    """Recursively convert native Python floats to decimal.Decimal.

    boto3's DynamoDB resource-level API (Table.put_item) rejects native
    floats outright with "TypeError: Float types are not supported. Use
    Decimal types instead." -- this surfaced for real once a trip was
    submitted with a numeric budget (goal["budget"] is a plain float from
    the frontend's JSON body). Every item written to DynamoDB in this module
    is nested/arbitrary (goal dicts, agent proposals, final plans), so this
    is applied generically here rather than patching each float field by
    hand at every call site. Uses Decimal(str(x)) rather than Decimal(x)
    directly to avoid binary-float imprecision (e.g. Decimal(2500.1) contains
    trailing-digit noise; Decimal(str(2500.1)) does not).
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _floats_to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(v) for v in value]
    return value


def create_trip_record(trip_id: str, user_id: str, goal: Dict) -> Dict:
    """
    Create initial trip record in DynamoDB.

    Args:
        trip_id: Unique trip ID
        user_id: Cognito user ID
        goal: User's trip goal/preferences

    Returns:
        Created item
    """
    table = get_table()
    item = {
        "PK": f"TRIP#{trip_id}",
        "SK": "META",
        "userId": user_id,
        "goal": _floats_to_decimal(goal),
        "status": "initializing",
        "round": 0,
        "timestamp": datetime.utcnow().isoformat(),
    }
    table.put_item(Item=item)
    return item


def write_agent_proposal(trip_id: str, round_num: int, agent_name: str, proposal: Dict) -> None:
    """
    Write agent proposal to DynamoDB.

    Args:
        trip_id: Trip ID
        round_num: Negotiation round number
        agent_name: Name of agent (itinerary, budget, logistics, booking)
        proposal: Proposal/verdict object
    """
    table = get_table()
    item = {
        "PK": f"TRIP#{trip_id}",
        "SK": f"ROUND#{round_num}#AGENT#{agent_name}",
        "proposal": _floats_to_decimal(proposal),
        "status": proposal.get("status", "proposed"),
        "objection": proposal.get("objection"),
        "round": round_num,
        "timestamp": datetime.utcnow().isoformat(),
    }
    table.put_item(Item=item)


def get_negotiation_history(trip_id: str) -> List[Dict]:
    """
    Retrieve full negotiation history for a trip.

    Args:
        trip_id: Trip ID

    Returns:
        List of all proposals/verdicts in order
    """
    table = get_table()
    response = table.query(KeyConditionExpression=f"PK = :pk", ExpressionAttributeValues={":pk": f"TRIP#{trip_id}"})
    return response.get("Items", [])


def finalize_trip(trip_id: str, final_plan: Dict, unresolved_objections: List = None) -> None:
    """
    Write final trip plan to DynamoDB.

    Args:
        trip_id: Trip ID
        final_plan: Final itinerary object
        unresolved_objections: List of objections that couldn't be resolved (if any)
    """
    table = get_table()
    item = {
        "PK": f"TRIP#{trip_id}",
        "SK": "FINAL",
        "proposal": _floats_to_decimal(final_plan),
        "unresolved_objections": _floats_to_decimal(unresolved_objections or []),
        "status": "finalized",
        "timestamp": datetime.utcnow().isoformat(),
    }
    table.put_item(Item=item)


def list_trips_for_user(user_id: str) -> List[Dict]:
    """List trip META items for a user via the UserIdIndex GSI (see infra/dynamodb.tf)."""
    table = get_table()
    response = table.query(
        IndexName="UserIdIndex",
        KeyConditionExpression="userId = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    return response.get("Items", [])
