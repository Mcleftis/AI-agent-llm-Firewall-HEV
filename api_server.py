"""
api_server.py
─────────────
FastAPI microservice that exposes the Neuro-Symbolic AI engine
(full_system.py) as a decoupled REST API.

Endpoints
---------
GET  /health              → liveness probe
POST /api/v1/intent       → driver-intent inference via get_driver_intent()
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from full_system import get_driver_intent

# =============================================================================
# CONSTANTS
# =============================================================================

API_HOST    = "0.0.0.0"
API_PORT    = 8000
API_VERSION = "v1"
APP_TITLE   = "Neuro-Symbolic HEV Control API"
APP_DESC    = (
    "REST wrapper around the Neuro-Symbolic driver-intent engine "
    "and the Digital Twin physics simulation."
)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# LIFESPAN  (startup / shutdown hooks)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup logic before serving; cleanup on shutdown."""
    logger.info("🚀 API Server starting – importing AI engine models…")
    # Models are pre-loaded at import time in full_system.py (module-level).
    # This hook is the right place to add future async warm-up tasks.
    logger.info("✅ API Server ready.")
    yield
    logger.info("🛑 API Server shutting down.")

# =============================================================================
# APP FACTORY
# =============================================================================

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESC,
    version=API_VERSION,
    lifespan=lifespan,
)

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class HealthResponse(BaseModel):
    status:  str = Field(..., examples=["ok"])
    version: str = Field(..., examples=[API_VERSION])
    message: str = Field(..., examples=["All systems operational."])


class IntentRequest(BaseModel):
    user_prompt: str = Field(
        ...,
        min_length=1,
        max_length=512,
        examples=["Drive me home quickly but save battery."],
        description="Natural-language command from the driver.",
    )


class IntentResponse(BaseModel):
    mode:           str   = Field(..., examples=["ECO"])
    aggressiveness: float = Field(..., ge=0.0, le=1.0, examples=[0.2])
    reasoning:      str   = Field(..., examples=["Symbolic Guardrail: Eco Mode explicitly requested."])

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    tags=["Infrastructure"],
)
async def health_check() -> HealthResponse:
    """
    Returns **200 OK** when the API process and the underlying AI engine
    are fully initialised and ready to serve requests.
    """
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        message="All systems operational.",
    )


@app.post(
    f"/api/{API_VERSION}/intent",
    response_model=IntentResponse,
    status_code=status.HTTP_200_OK,
    summary="Infer driver intent from a natural-language prompt",
    tags=["AI Inference"],
)
async def infer_intent(payload: IntentRequest) -> IntentResponse:
    """
    Passes the driver's **user_prompt** through the Neuro-Symbolic engine
    (`get_driver_intent`) and returns the resolved driving mode,
    aggressiveness score, and the engine's reasoning chain.

    - **mode** – one of `SPORT | NORMAL | ECO | EMERGENCY_COAST`
    - **aggressiveness** – float in `[0.0, 1.0]`
    - **reasoning** – human-readable explanation from the AI/Symbolic layer
    """
    logger.info("POST /api/%s/intent | prompt=%r", API_VERSION, payload.user_prompt)

    try:
        result: dict = get_driver_intent(forced_prompt=payload.user_prompt)
    except Exception as exc:
        logger.exception("get_driver_intent() raised an unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI engine error: {exc}",
        ) from exc

    # Validate that the engine returned all expected keys
    required_keys = {"mode", "aggressiveness", "reasoning"}
    if not required_keys.issubset(result):
        missing = required_keys - result.keys()
        logger.error("Engine response missing keys: %s", missing)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Incomplete response from AI engine. Missing keys: {missing}",
        )

    try:
        return IntentResponse(
            mode=result["mode"],
            aggressiveness=float(result["aggressiveness"]),
            reasoning=result["reasoning"],
        )
    except (ValueError, TypeError) as exc:
        logger.exception("Response serialisation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response serialisation error: {exc}",
        ) from exc


# =============================================================================
# GLOBAL EXCEPTION HANDLER  (catch-all safety net)
# =============================================================================

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    logger.critical("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal error occurred."},
    )


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info",
    )