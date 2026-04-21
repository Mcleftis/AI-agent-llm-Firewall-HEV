"""
api_server.py
─────────────
FastAPI microservice that exposes the Neuro-Symbolic AI engine
(full_system.py) as a decoupled REST API.
"""

import logging
import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Callable, Awaitable

import uvicorn
from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Υποθέτουμε ότι το get_driver_intent υπάρχει στο full_system.py (ή AI_agent.py)
from full_system import get_driver_intent

# =============================================================================
# CONSTANTS & SECRETS
# =============================================================================

API_HOST    = "0.0.0.0" # nosec
API_PORT    = 8000
API_VERSION = "v1"
APP_TITLE   = "Neuro-Symbolic HEV Control API"
APP_DESC    = "REST wrapper around the Neuro-Symbolic driver-intent engine and Digital Twin."

DEFAULT_AGGRESSIVENESS = 0.5

# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

# Εμποδίζει το "Context Bleeding" στο LLM όταν έρχονται ταυτόχρονα requests (HPC Batch)
inference_lock = asyncio.Lock()

# =============================================================================
# LIFESPAN  (startup / shutdown hooks) & WARMUP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup logic before serving; cleanup on shutdown."""
    logger.info("🚀 API Server starting – Initializing AI Engine...")
    
    # --- SENIOR TRICK: SERVER-SIDE AI WARMUP ---
    logger.info("🔥 Warming up AI models (LLM & PyTorch) in background... Please wait.")
    try:
        # Τρέχουμε το inference εικονικά μία φορά
        dummy_result: Dict[str, Any] = await asyncio.to_thread(get_driver_intent, forced_prompt="warmup system")
        logger.info(f"✅ AI Warmup Complete! Systems hot. Dummy result: {dummy_result.get('mode')}")
    except Exception as e:
        logger.warning(f"⚠️ AI Warmup failed or timed out: {e}")
        
    logger.info("🟢 API Server is fully ONLINE and ready to accept traffic.")
    yield
    logger.info("🛑 API Server shutting down.")

# =============================================================================
# APP FACTORY & MIDDLEWARE
# =============================================================================

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESC,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url=None,      # 🚀 ΚΛΕΙΝΕΙ ΤΟ /docs (Swagger) για Security
    redoc_url=None,     # 🚀 ΚΛΕΙΝΕΙ ΤΟ /redoc
    openapi_url=None    # 🚀 ΚΛΕΙΝΕΙ ΤΟ /openapi.json
)

# 🛡️ WAF MIDDLEWARE (Πρέπει να μπει ΠΡΙΝ το CORS)
@app.middleware("http")
async def block_sensitive_files(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    # Κόβει αιτήματα που ψάχνουν κρυφά αρχεία ή κάνουν Path Traversal
    suspicious_paths = ["/.env", "/.git", "/etc/passwd", "../"]
    if any(sp in request.url.path for sp in suspicious_paths):
        logger.warning(f"🛡️ WAF Blocked malicious request: {request.client.host} targeting {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, 
            content={"detail": "Security Exception: Blocked by WAF"}
        )
    return await call_next(request)

# 🌐 CORS MIDDLEWARE (ΑΣΦΑΛΕΣ ΓΙΑ PRODUCTION)
app.add_middleware(
    CORSMiddleware,
    # Δέχεται αιτήματα ΜΟΝΟ από το τοπικό Streamlit Frontend (ή όποιο domain προσθέσεις εδώ)
    allow_origins=[
        "http://localhost:8501", 
        "http://127.0.0.1:8501",
        "https://localhost:8501" # Αν και το Frontend τρέχει με SSL
    ], 
    allow_credentials=True,
    allow_methods=["GET", "POST"], # Κόψαμε το "*" και αφήσαμε μόνο GET/POST (Αρχή Ελάχιστων Προνομίων)
    allow_headers=["Content-Type", "Authorization", "Accept"],
)
# =============================================================================
# PYDANTIC SCHEMAS (Data Validation)
# =============================================================================

class HealthResponse(BaseModel):
    status:  str = Field(..., examples=["ok"])
    version: str = Field(..., examples=[API_VERSION])
    message: str = Field(..., examples=["All systems operational."])

class IntentRequest(BaseModel):
    user_prompt: str = Field(default="", max_length=512)
    command: str = Field(default="", max_length=512)

class IntentResponse(BaseModel):
    mode:           str   = Field(..., examples=["ECO"])
    aggressiveness: float = Field(..., ge=0.0, le=1.0)
    reasoning:      str   = Field(...)

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK, tags=["Infrastructure"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION, message="All systems operational.")

@app.get(f"/api/{API_VERSION}/vehicle/telemetry", status_code=status.HTTP_200_OK, tags=["Telemetry"])
async def telemetry_mock() -> Dict[str, Any]:
    return {"status": "connected", "speed": 0, "power": 0}

@app.post(f"/api/{API_VERSION}/intent", response_model=IntentResponse, status_code=status.HTTP_200_OK, tags=["AI Inference"])
async def infer_intent(payload: IntentRequest) -> IntentResponse:
    actual_prompt: str = payload.user_prompt if payload.user_prompt else payload.command
    
    if not actual_prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail="Missing valid prompt in payload"
        )

    logger.info("POST /api/%s/intent | prompt='%s'", API_VERSION, actual_prompt)

    async with inference_lock:
        try:
            result: Dict[str, Any] = await asyncio.to_thread(get_driver_intent, forced_prompt=actual_prompt)
        except Exception as exc:
            logger.exception("get_driver_intent() raised an error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail=f"AI engine error: {exc}"
            )

    final_mode: str = result.get("selected_mode") or result.get("mode") or "NORMAL"
    final_aggr: float = result.get("throttle_sensitivity") or result.get("aggressiveness") or DEFAULT_AGGRESSIVENESS
    final_reasoning: str = result.get("reasoning") or "No reasoning provided by AI."

    try:
        return IntentResponse(
            mode=str(final_mode).upper(),
            aggressiveness=float(final_aggr),
            reasoning=str(final_reasoning),
        )
    except (ValueError, TypeError) as exc:
        logger.exception("Response serialisation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Response serialisation error: {exc}"
        )

# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.critical("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal error occurred."},
    )

if __name__ == "__main__":
    # --- ΔΥΝΑΜΙΚΗ ΕΥΡΕΣΗ ΤΩΝ SSL ΠΙΣΤΟΠΟΙΗΤΙΚΩΝ ---
    # Βρίσκει τον φάκελο στον οποίο βρίσκεται το api_server.py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Φτιάχνει το μονοπάτι για τον φάκελο certs
    ssl_keyfile = os.path.join(BASE_DIR, "certs", "key.pem")
    ssl_certfile = os.path.join(BASE_DIR, "certs", "cert.pem")
    
    if os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
        logger.info(f"🔒 SSL Certificates found in {os.path.join(BASE_DIR, 'certs')}. Starting server with HTTPS...")
        uvicorn.run("api_server:app", host=API_HOST, port=API_PORT, reload=False, log_level="info", 
                    ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
    else:
        logger.warning(f"⚠️ SSL Certificates NOT found at {ssl_keyfile}. Starting server with HTTP (Insecure mode).")
        uvicorn.run("api_server:app", host=API_HOST, port=API_PORT, reload=False, log_level="info")
    else:
        logger.warning('?? No SSL Certificates found. Starting server in HTTP mode...')
        uvicorn.run('api_server:app', host=API_HOST, port=API_PORT)
