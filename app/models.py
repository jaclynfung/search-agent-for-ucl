from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentRequest:
    query: str


@dataclass
class IntentResult:
    intent: str
    entity: str | None
    reasons: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    tool_name: str
    answer: str
    sources: list[str]
    confidence: str


@dataclass
class AgentResponse:
    intent: str
    entity: str | None
    answer: str
    sources: list[str]
    confidence: str
    routing_reason: str
    llm_used: bool = False


@dataclass
class HealthResponse:
    status: str
