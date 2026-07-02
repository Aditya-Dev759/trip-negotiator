"""
Local development launcher for the FastAPI backend.

Installs an in-memory mock in place of DynamoDB (shared/local_mock_db.py),
then boots the real app (api/main.py) with uvicorn. api/main.py itself has
no local-only code in it -- this file exists purely to make local iteration
painless, and to give you the standard FastAPI dev experience:

    Swagger UI:  http://localhost:3001/docs
    ReDoc:       http://localhost:3001/redoc
    OpenAPI JSON: http://localhost:3001/openapi.json

Run it exactly as before:  python local_api_server.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from dotenv import load_dotenv
load_dotenv()
print("[Backend Startup] Loaded environment variables from .env")

from shared.logging_utils import configure_logging, get_logger

configure_logging()
log = get_logger("local_api_server")

# Install the in-memory mock BEFORE importing api.main, so every module that
# does `from shared.dynamo_utils import ...` (api.main itself, and every
# agents/*/handler.py) picks up the mocked functions instead of trying to
# hit real AWS with no credentials/region configured.
from shared.local_mock_db import install as install_local_db

install_local_db()

import uvicorn

from api.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3001))
    log.info("Starting FastAPI app on http://localhost:%d (interactive docs at /docs)", port)
    log.info("Dynamic web search and Groq LLM calls will execute on requests.")
    log.info("Set LOG_LEVEL=DEBUG in .env to see full prompt/response bodies.")
    # reload=False is intentional: uvicorn's auto-reloader re-imports api.main
    # in a fresh subprocess on every code change, which would bypass the
    # in-memory mock installed above. For a live-reload FastAPI dev loop
    # against real AWS resources (no mock needed), run instead:
    #   uvicorn api.main:app --reload --port 3001
    uvicorn.run(app, host="0.0.0.0", port=port)
