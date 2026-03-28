from __future__ import annotations

import re

from app.data import COURSES, PROFESSORS
from app.models import IntentResult


INTENT_OFFICE_HOUR = "office_hour"
INTENT_PROFESSOR_INFO = "professor_info"
INTENT_COURSE_INFO = "course_info"
INTENT_UNKNOWN = "unknown"


def classify_intent(query: str) -> IntentResult:
    lowered = query.lower()
    reasons: list[str] = []

    entity = _extract_course(query) or _extract_professor(query)

    if any(
        token in lowered
        for token in ["office hour", "office hours", "oh", "opening hours", "open hours", "hours"]
    ):
        reasons.append("Detected hours-related language in the query.")
        return IntentResult(intent=INTENT_OFFICE_HOUR, entity=entity, reasons=reasons)

    if any(token in lowered for token in ["professor", "research", "faculty", "email", "staff", "people", "contact"]):
        reasons.append("Detected staff or faculty-related language in the query.")
        return IntentResult(intent=INTENT_PROFESSOR_INFO, entity=entity, reasons=reasons)

    if any(
        token in lowered
        for token in [
            "programme",
            "programmes",
            "course",
            "courses",
            "study",
            "school",
            "schools",
            "institute",
            "institutes",
            "ucl200",
            "news",
            "events",
        ]
    ):
        reasons.append("Detected programme, institute, or Bartlett section language in the query.")
        return IntentResult(intent=INTENT_COURSE_INFO, entity=entity, reasons=reasons)

    if _extract_course(query):
        reasons.append("Detected a programme or course name from the local catalog.")
        return IntentResult(intent=INTENT_COURSE_INFO, entity=entity, reasons=reasons)

    if _extract_professor(query):
        reasons.append("Detected a staff name from the local directory.")
        return IntentResult(intent=INTENT_PROFESSOR_INFO, entity=entity, reasons=reasons)

    reasons.append("No strong course, professor, or office-hour signal was found.")
    return IntentResult(intent=INTENT_UNKNOWN, entity=entity, reasons=reasons)


def classify_intent_with_override(query: str, intent: str, entity: str | None, reason: str) -> IntentResult:
    fallback = classify_intent(query)
    allowed = {INTENT_OFFICE_HOUR, INTENT_PROFESSOR_INFO, INTENT_COURSE_INFO, INTENT_UNKNOWN}
    resolved_intent = intent if intent in allowed else fallback.intent
    resolved_entity = entity or fallback.entity
    return IntentResult(
        intent=resolved_intent,
        entity=resolved_entity,
        reasons=[f"Gemini classified the query: {reason}"],
    )


def _extract_course(query: str) -> str | None:
    lowered = query.lower()
    for course in COURSES:
        if course["course"].lower() in lowered:
            return course["course"]
        for alias in course["aliases"]:
            if alias.lower() in lowered:
                return course["course"]
    return None


def _extract_professor(query: str) -> str | None:
    lowered = query.lower()
    for professor in PROFESSORS:
        name = professor["name"]
        if name.lower() in lowered:
            return name
        last_name = name.split()[-1].lower()
        if last_name in lowered:
            return name
    return None
