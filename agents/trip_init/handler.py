"""
RETIRED -- do not deploy this module.

This was the original HTTP entrypoint Lambda: it hand-rolled routing for
POST /trips, GET /trips, and GET /trips/{id}, then started a Step Functions
execution. It has been superseded by api/main.py, a FastAPI app (wrapped in
Mangum) that already implements the same behaviour more robustly -- request
validation via Pydantic, OpenAPI docs, and it never fell out of sync when
new routes (GET /locations/search, GET /exchange-rate) were added, unlike
this file, which never learned about them.

infra/lambda.tf no longer builds or deploys a Lambda from this file --
aws_lambda_function.api (image-based, api.main.handler) is the real HTTP
entrypoint now, see infra/apigateway.tf. This file could not be deleted
from disk in this session (Windows file lock on the mounted folder); it is
kept only as an inert stub so nothing here can be mistaken for live code.
Delete agents/trip_init/ entirely once you're back on your own machine.
"""

def lambda_handler(event, context):  # pragma: no cover -- intentionally inert
    raise RuntimeError(
        "agents/trip_init/handler.py is retired and not deployed by "
        "infra/lambda.tf. See api/main.py (deployed as aws_lambda_function.api) "
        "for the current HTTP entrypoint."
    )
