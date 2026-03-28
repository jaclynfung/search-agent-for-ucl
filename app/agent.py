from __future__ import annotations

from app.intents import (
    INTENT_COURSE_INFO,
    INTENT_OFFICE_HOUR,
    INTENT_PROFESSOR_INFO,
    INTENT_UNKNOWN,
    classify_intent,
    classify_intent_with_override,
)
from app.llm import GeminiAnswerRefiner, GeminiIntentClassifier
from app.models import AgentRequest, AgentResponse
from app.tools import FaissTool, SearchTool


class BartlettInfoAgent:
    def __init__(self) -> None:
        self.search_tool = SearchTool()
        self.faiss_tool = FaissTool()
        self.intent_classifier = GeminiIntentClassifier()
        self.answer_refiner = GeminiAnswerRefiner()

    def handle(self, request: AgentRequest) -> AgentResponse:
        intent_result = self._resolve_intent(request.query)
        routing_reason = "; ".join(intent_result.reasons)

        if intent_result.intent == INTENT_PROFESSOR_INFO:
            retrieval = self.faiss_tool.run(
                query=request.query,
                intent=intent_result.intent,
                entity=intent_result.entity,
            )
        elif intent_result.intent in {INTENT_COURSE_INFO, INTENT_OFFICE_HOUR}:
            retrieval = self._best_retrieval(
                query=request.query,
                intent=intent_result.intent,
                entity=intent_result.entity,
            )
        else:
            retrieval = self._best_retrieval(
                query=request.query,
                intent=INTENT_COURSE_INFO,
                entity=intent_result.entity,
            )

        refined_answer = self.answer_refiner.refine(
            query=request.query,
            intent=intent_result.intent,
            entity=intent_result.entity,
            draft_answer=retrieval.answer,
            sources=retrieval.sources,
            routing_reason=routing_reason,
        )

        return AgentResponse(
            intent=intent_result.intent,
            entity=intent_result.entity,
            answer=refined_answer or retrieval.answer,
            sources=retrieval.sources,
            confidence=retrieval.confidence,
            routing_reason=routing_reason,
            llm_used=bool(refined_answer),
        )

    def _resolve_intent(self, query: str):
        llm_intent = self.intent_classifier.classify(query=query)
        if llm_intent is not None:
            return classify_intent_with_override(
                query=query,
                intent=llm_intent.intent,
                entity=llm_intent.entity,
                reason=llm_intent.reason,
            )
        return classify_intent(query)

    def _best_retrieval(self, query: str, intent: str, entity: str | None):
        faiss_result = self.faiss_tool.run(query=query, intent=intent, entity=entity)
        search_result = self.search_tool.run(query=query, intent=intent, entity=entity)
        return self._choose_better_result(faiss_result, search_result)

    def _choose_better_result(self, left, right):
        ranking = {"high": 3, "medium": 2, "low": 1}
        left_score = ranking.get(left.confidence, 0) + (1 if left.sources else 0)
        right_score = ranking.get(right.confidence, 0) + (1 if right.sources else 0)
        return left if left_score >= right_score else right
