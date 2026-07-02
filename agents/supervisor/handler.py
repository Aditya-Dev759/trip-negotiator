import json
import sys
from pathlib import Path

# Add shared folder to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.dynamo_utils import finalize_trip, get_table
from shared.logging_utils import get_logger

log = get_logger("supervisor")


def lambda_handler(event, context):
    """
    Supervisor Lambda: Finalizes negotiation and writes final trip plan to DynamoDB.
    """
    trip_id = event.get("trip_id")
    itinerary = event.get("itinerary", {})
    all_approved = event.get("allApproved", False)

    unresolved_objections = []
    if not all_approved:
        # Collect any objections since we are force-finalizing
        for agent_key in ["budget_verdict", "logistics_verdict", "booking_verdict"]:
            verdict = event.get(agent_key, {})
            if verdict.get("status") == "rejected" and verdict.get("objection"):
                unresolved_objections.append({
                    "agent": agent_key.replace("_verdict", ""),
                    "objection": verdict.get("objection")
                })

    log.info(
        "=== Supervisor | trip=%s | finalizing round=%s all_approved=%s unresolved_objections=%d ===",
        trip_id, event.get("round"), all_approved, len(unresolved_objections),
    )

    # 1. Update trip status to finalized in META record in DynamoDB
    table = get_table()
    try:
        table.update_item(
            Key={"PK": f"TRIP#{trip_id}", "SK": "META"},
            UpdateExpression="SET #s = :status, #r = :round",
            ExpressionAttributeNames={"#s": "status", "#r": "round"},
            ExpressionAttributeValues={
                ":status": "finalized",
                ":round": event.get("round", 3)
            }
        )
    except Exception as e:
        log.error("Failed to update trip metadata: %s", e)

    # 2. Write the FINAL record containing the finalized itinerary and objections
    finalize_trip(trip_id, itinerary, unresolved_objections)
    log.info("=== Trip %s finalized ===", trip_id)

    return {
        "status": "success",
        "trip_id": trip_id,
        "final_itinerary": itinerary,
        "unresolved_objections": unresolved_objections
    }
