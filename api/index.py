"""DREX - Vercel serverless API entry point"""
import os
import sys
import json
from typing import Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Disable GUI/voice modules for serverless
os.environ["DREX_GUI_ENABLED"] = "false"
os.environ["DREX_VOICE_ENABLED"] = "false"

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

app = FastAPI(
    title="DREX AI Assistant API",
    version="1.0.0",
    description="AI-powered desktop assistant - Web API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    provider: str
    session_id: Optional[str] = None


class ProviderRequest(BaseModel):
    provider: str


# Lazy-init orchestrator singleton
_orchestrator = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        try:
            from utils.logger import setup_logger
            setup_logger()
        except Exception:
            pass

        from config import get_config
        cfg = get_config()
        cfg.app.gui_enabled = False
        cfg.app.voice_enabled = False

        # Suppress noisy logs in serverless
        os.environ["DREX_LOG_LEVEL"] = "WARNING"

        from core.orchestrator import Orchestrator
        _orchestrator = Orchestrator()
    return _orchestrator


@app.on_event("startup")
async def startup():
    """Initialize orchestrator on cold start."""
    try:
        get_orchestrator()
    except Exception as e:
        print(f"Orchestrator init warning (non-fatal): {e}")


@app.get("/")
async def root():
    return {
        "name": "DREX AI Assistant",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat - POST (send message)",
            "status": "/status - GET (providers & health)",
            "providers": "/providers - GET (list providers)",
            "health": "/health - GET (health check)"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/status")
async def status():
    try:
        from brain.ai_router import AIRouter
        router_status = AIRouter().get_status()
        return {"status": "ok", "providers": router_status}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/providers")
async def providers():
    try:
        from brain.ai_router import AIRouter
        router = AIRouter()
        status_data = router.get_status()
        available = [
            p for p, info in status_data.get("providers", {}).items()
            if info.get("available")
        ]
        return {"available_providers": available, "default": status_data.get("default")}
    except Exception as e:
        return {"available_providers": [], "default": None, "error": str(e)}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        orch = get_orchestrator()

        # Switch provider if specified
        if request.provider:
            try:
                orch.switch_ai_provider(request.provider)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to switch provider: {e}"
                )

        # Get AI response
        response = orch.process(request.message, voice_response=False)

        # Get current provider info
        try:
            from config import get_config
            current_provider = get_config().ai.default_provider
        except Exception:
            current_provider = "unknown"

        return ChatResponse(
            response=response,
            provider=current_provider,
            session_id=request.session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/switch_provider")
async def switch_provider(request: ProviderRequest):
    try:
        from config import get_config
        cfg = get_config()
        cfg.ai.default_provider = request.provider
        return {"status": "ok", "provider": request.provider}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))