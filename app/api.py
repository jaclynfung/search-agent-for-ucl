from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from app.agent import BartlettInfoAgent
from app.models import AgentRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")
    logger.info("dotenv_loaded path=%s", BASE_DIR / ".env")
else:
    logger.warning("dotenv_missing install python-dotenv to auto-load .env files")

app = FastAPI(title="UCL Bartlett Info Agent", version="0.1.0")
agent = BartlettInfoAgent()
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    intent: str
    entity: str | None
    answer: str
    sources: list[str]
    confidence: str
    routing_reason: str
    llm_used: bool


class HealthResponse(BaseModel):
    status: str


class LLMDebugResponse(BaseModel):
    dotenv_path: str
    dotenv_exists: bool
    dotenv_loader_available: bool
    gemini_key_present: bool
    gemini_key_prefix: str | None
    gemini_model: str | None
    gemini_fallback_model: str | None


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/debug/llm", response_model=LLMDebugResponse)
def debug_llm() -> LLMDebugResponse:
    key = os.getenv("GEMINI_API_KEY")
    return LLMDebugResponse(
        dotenv_path=str(BASE_DIR / ".env"),
        dotenv_exists=(BASE_DIR / ".env").exists(),
        dotenv_loader_available=load_dotenv is not None,
        gemini_key_present=bool(key),
        gemini_key_prefix=(key[:6] if key else None),
        gemini_model=os.getenv("GEMINI_MODEL"),
        gemini_fallback_model=os.getenv("GEMINI_FALLBACK_MODEL"),
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    logger.info("api_query_received query=%r", request.query[:200])
    response = agent.handle(AgentRequest(query=request.query))
    logger.info(
        "api_query_completed intent=%s entity=%r llm_used=%s confidence=%s sources=%d",
        response.intent,
        response.entity,
        response.llm_used,
        response.confidence,
        len(response.sources),
    )
    return QueryResponse(
        intent=response.intent,
        entity=response.entity,
        answer=response.answer,
        sources=response.sources,
        confidence=response.confidence,
        routing_reason=response.routing_reason,
        llm_used=response.llm_used,
    )
