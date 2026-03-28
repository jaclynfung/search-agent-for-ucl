from __future__ import annotations

import logging
import os

from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None

logger = logging.getLogger(__name__)


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
            logger.info("gemini_disabled api_key_present=%s sdk_ready=%s", bool(self.api_key), genai is not None and types is not None)
            return None

        client = self._get_client()
        for model_name in [self.model, self.fallback_model]:
            try:
                logger.info("gemini_generate_start model=%s", model_name)
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                logger.warning("gemini_generate_failed model=%s error=%s", model_name, exc)
                continue
        logger.warning("gemini_generate_exhausted tried_models=%s", [self.model, self.fallback_model])
        return None


class GeminiIntentClassifier(GeminiBase):
    def classify(self, *, query: str) -> GeminiIntentOutput | None:
        if not self.enabled:
            logger.info("gemini_intent_skip reason=disabled")
            return None

        logger.info("gemini_intent_start query=%r", query[:200])
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
            logger.warning("gemini_intent_no_response")
            return None

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, GeminiIntentOutput):
            logger.info("gemini_intent_success intent=%s entity=%r reason=%r", parsed.intent, parsed.entity, parsed.reason)
            return parsed
        if isinstance(parsed, dict):
            try:
                validated = GeminiIntentOutput.model_validate(parsed)
                logger.info("gemini_intent_success intent=%s entity=%r reason=%r", validated.intent, validated.entity, validated.reason)
                return validated
            except Exception as exc:
                logger.warning("gemini_intent_parse_failed error=%s payload=%r", exc, parsed)
                return None
        logger.warning("gemini_intent_unparsed parsed_type=%s", type(parsed).__name__)
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
            logger.info("gemini_refine_skip reason=disabled")
            return None

        logger.info("gemini_refine_start intent=%s entity=%r sources=%d", intent, entity, len(sources))
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
            logger.warning("gemini_refine_no_response")
            return None

        text = getattr(response, "text", None)
        cleaned = (text or "").strip()
        if cleaned:
            logger.info("gemini_refine_success chars=%d preview=%r", len(cleaned), cleaned[:160])
        else:
            logger.warning("gemini_refine_empty_text")
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
