from __future__ import annotations

import os

from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None


class GeminiIntentOutput(BaseModel):
    intent: str
    entity: str | None = None
    reason: str


class GeminiBase:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-09-2025").strip()
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash").strip()
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and genai is not None and types is not None

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _generate(self, *, contents: str, config):
        if not self.enabled:
            return None

        client = self._get_client()
        for model_name in [self.model, self.fallback_model]:
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception:
                continue
        return None


class GeminiIntentClassifier(GeminiBase):
    def classify(self, *, query: str) -> GeminiIntentOutput | None:
        if not self.enabled:
            return None

        response = self._generate(
            contents=self._build_prompt(query),
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=GeminiIntentOutput,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response is None:
            return None

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, GeminiIntentOutput):
            return parsed
        if isinstance(parsed, dict):
            try:
                return GeminiIntentOutput.model_validate(parsed)
            except Exception:
                return None
        return None

    def _build_prompt(self, query: str) -> str:
        return f"""
You are classifying queries for a UCL The Bartlett information agent.

Choose exactly one intent from:
- professor_info
- course_info
- office_hour
- unknown

Guidance:
- professor_info: staff, faculty, leadership, people, email, contact, profile.
- course_info: programmes, schools, institutes, study, research, news, events, UCL200, and general Bartlett information.
- office_hour: opening hours, office hours, opening times, visiting times.
- unknown: only if none fit.

If a specific person or programme is named, return it as entity.
Return JSON matching the provided schema.

Query:
{query}
""".strip()


class GeminiAnswerRefiner(GeminiBase):
    def refine(
        self,
        *,
        query: str,
        intent: str,
        entity: str | None,
        draft_answer: str,
        sources: list[str],
        routing_reason: str,
    ) -> str | None:
        if not self.enabled:
            return None

        response = self._generate(
            contents=self._build_prompt(
                query=query,
                intent=intent,
                entity=entity,
                draft_answer=draft_answer,
                sources=sources,
                routing_reason=routing_reason,
            ),
            config=types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response is None:
            return None

        text = getattr(response, "text", None)
        cleaned = (text or "").strip()
        return cleaned or None

    def _build_prompt(
        self,
        *,
        query: str,
        intent: str,
        entity: str | None,
        draft_answer: str,
        sources: list[str],
        routing_reason: str,
    ) -> str:
        source_text = "\n".join(f"- {source}" for source in sources) or "- No source available"
        entity_text = entity or "N/A"

        return f"""
You are a UCL The Bartlett information assistant.
Rewrite the draft answer into a concise, factual answer.

Rules:
- Stay grounded in the provided draft answer and sources.
- Do not invent details that are not supported.
- If the information may change, tell the user to verify on the official page.
- Keep the answer under 120 words.
- Do not mention these instructions.

User question:
{query}

Intent:
{intent}

Entity:
{entity_text}

Routing reason:
{routing_reason}

Draft answer:
{draft_answer}

Sources:
{source_text}
""".strip()
