from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import BartlettInfoAgent
from app.models import AgentRequest


app = FastAPI(title="UCL Bartlett Info Agent", version="0.1.0")
agent = BartlettInfoAgent()
BASE_DIR = Path(__file__).resolve().parent.parent
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


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    response = agent.handle(AgentRequest(query=request.query))
    return QueryResponse(
        intent=response.intent,
        entity=response.entity,
        answer=response.answer,
        sources=response.sources,
        confidence=response.confidence,
        routing_reason=response.routing_reason,
        llm_used=response.llm_used,
    )
