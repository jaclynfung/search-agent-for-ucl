from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

from app.data import COURSES, PROFESSORS
from app.intents import INTENT_COURSE_INFO, INTENT_OFFICE_HOUR, INTENT_PROFESSOR_INFO
from app.models import RetrievalResult
from app.vector_store import BartlettVectorStore


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


class SearchTool:
    name = "search"
    search_endpoint = "https://duckduckgo.com/html/"
    default_domains = (
        "ucl.ac.uk",
    )
    allowed_path_prefixes = (
        "/bartlett/study",
        "/bartlett/research",
        "/bartlett/our-schools-and-institutes",
        "/bartlett/people",
        "/bartlett/ideas",
        "/bartlett/engage",
        "/bartlett/news-and-events",
        "/bartlett/about",
        "/bartlett/architecture",
        "/bartlett/planning",
        "/bartlett/construction",
        "/bartlett/environment-energy-resources",
        "/bartlett/development",
    )

    def run(self, query: str, intent: str, entity: str | None) -> RetrievalResult:
        search_query = self._build_search_query(query=query, intent=intent, entity=entity)
        web_hits = self._web_search(search_query)
        if web_hits:
            return self._format_web_result(web_hits)

        if intent == INTENT_OFFICE_HOUR:
            return self._search_office_hour(entity)
        if intent == INTENT_COURSE_INFO:
            return self._search_course(entity)
        return RetrievalResult(
            tool_name=self.name,
            answer="I could not find a strong public-web answer for that request yet.",
            sources=[],
            confidence="low",
        )

    def _build_search_query(self, query: str, intent: str, entity: str | None) -> str:
        if query.strip():
            base_query = query.strip()
        elif entity:
            base_query = entity
        else:
            base_query = "UCL Bartlett"

        if intent == INTENT_OFFICE_HOUR:
            base_query = f"{base_query} office hours"
        elif intent == INTENT_COURSE_INFO and entity:
            base_query = f"{entity} UCL Bartlett programme"
        elif intent == INTENT_PROFESSOR_INFO and entity:
            base_query = f"{entity} UCL Bartlett people"

        domain_terms = " OR ".join(f"site:{domain}" for domain in self.default_domains)
        return f"{base_query} ({domain_terms})"

    def _web_search(self, query: str) -> list[SearchHit]:
        params = urllib.parse.urlencode({"q": query})
        url = f"{self.search_endpoint}?{params}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return []

        return self._parse_duckduckgo_html(body)

    def _parse_duckduckgo_html(self, body: str) -> list[SearchHit]:
        hits: list[SearchHit] = []
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>|'
            r'<a[^>]*class="result__a"[^>]*href="(?P<url2>[^"]+)"[^>]*>(?P<title2>.*?)</a>.*?'
            r'<div[^>]*class="result__snippet"[^>]*>(?P<snippet2>.*?)</div>',
            re.DOTALL,
        )

        for match in pattern.finditer(body):
            raw_url = match.group("url") or match.group("url2")
            raw_title = match.group("title") or match.group("title2")
            raw_snippet = match.group("snippet") or match.group("snippet2") or ""
            if not raw_url or not raw_title:
                continue

            clean_url = self._clean_html(raw_url)
            if not self._is_allowed_domain(clean_url):
                continue

            hits.append(
                SearchHit(
                    title=self._clean_html(raw_title),
                    url=clean_url,
                    snippet=self._clean_html(raw_snippet),
                )
            )
            if len(hits) >= 3:
                break

        return hits

    def _clean_html(self, value: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", value)
        cleaned = html.unescape(cleaned)
        return " ".join(cleaned.split())

    def _is_allowed_domain(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if not any(host.endswith(domain) for domain in self.default_domains):
            return False
        path = parsed.path.rstrip("/")
        return any(path.startswith(prefix) for prefix in self.allowed_path_prefixes)

    def _format_web_result(self, hits: list[SearchHit]) -> RetrievalResult:
        top_hit = hits[0]
        answer = f"{top_hit.title}: {top_hit.snippet}" if top_hit.snippet else top_hit.title
        return RetrievalResult(
            tool_name=self.name,
            answer=answer,
            sources=[hit.url for hit in hits],
            confidence="medium",
        )

    def _search_office_hour(self, entity: str | None) -> RetrievalResult:
        if not entity:
            return RetrievalResult(
                tool_name=self.name,
                answer="I need a Bartlett programme or staff name to look up office hours or contact details.",
                sources=[],
                confidence="low",
            )

        for course in COURSES:
            if course["course"] == entity:
                return RetrievalResult(
                    tool_name=self.name,
                    answer=f"{course['course']} office hours: {course['office_hours']}",
                    sources=[course["source"]],
                    confidence="medium",
                )

        for professor in PROFESSORS:
            if professor["name"] == entity:
                return RetrievalResult(
                    tool_name=self.name,
                    answer=f"{professor['name']} office hours: {professor['office_hours']}",
                    sources=[professor["source"]],
                    confidence="medium",
                )

        return RetrievalResult(
            tool_name=self.name,
            answer=f"I did not find office-hour data for '{entity}'.",
            sources=[],
            confidence="low",
        )

    def _search_course(self, entity: str | None) -> RetrievalResult:
        if not entity:
            return RetrievalResult(
                tool_name=self.name,
                answer="I need a programme name like Architecture BSc or MArch Architecture.",
                sources=[],
                confidence="low",
            )

        for course in COURSES:
            if course["course"] == entity:
                return RetrievalResult(
                    tool_name=self.name,
                    answer=(
                        f"{course['course']} is {course['title']}. "
                        f"{course['description']} Instructor info: {course['instructor']}"
                    ),
                    sources=[course["source"]],
                    confidence="medium",
                )

        return RetrievalResult(
            tool_name=self.name,
            answer=f"I did not find a course page for '{entity}'.",
            sources=[],
            confidence="low",
        )


class FaissTool:
    name = "faiss"

    def __init__(self) -> None:
        self.vector_store = BartlettVectorStore()

    def run(self, query: str, intent: str, entity: str | None) -> RetrievalResult:
        vector_result = self.vector_store.search(query=query, entity=entity, top_k=3)
        if vector_result is not None:
            return RetrievalResult(
                tool_name=self.name,
                answer=vector_result["answer"],
                sources=vector_result["sources"],
                confidence=vector_result["confidence"],
            )

        if intent == INTENT_PROFESSOR_INFO:
            return self._lookup_professor(entity)
        if intent == INTENT_COURSE_INFO:
            return self._lookup_course(entity)
        return RetrievalResult(
            tool_name=self.name,
            answer="The local knowledge base did not match that request.",
            sources=[],
            confidence="low",
        )

    def _lookup_professor(self, entity: str | None) -> RetrievalResult:
        if not entity:
            return RetrievalResult(
                tool_name=self.name,
                answer="I need a staff name to search the local Bartlett knowledge base.",
                sources=[],
                confidence="low",
            )

        for professor in PROFESSORS:
            if professor["name"] == entity:
                return RetrievalResult(
                    tool_name=self.name,
                    answer=(
                        f"{professor['name']} is a {professor['title']} at UCL The Bartlett. "
                        f"Research areas: {professor['research']}. "
                        f"Contact: {professor['email']}."
                    ),
                    sources=[professor["source"]],
                    confidence="high",
                )

        return RetrievalResult(
            tool_name=self.name,
            answer=f"I could not find professor data for '{entity}' in the local index.",
            sources=[],
            confidence="low",
        )

    def _lookup_course(self, entity: str | None) -> RetrievalResult:
        if not entity:
            return RetrievalResult(
                tool_name=self.name,
                answer="I need a course identifier to search the local course index.",
                sources=[],
                confidence="low",
            )

        for course in COURSES:
            if course["course"] == entity:
                return RetrievalResult(
                    tool_name=self.name,
                    answer=f"{course['course']}: {course['description']}",
                    sources=[course["source"]],
                    confidence="high",
                )

        return RetrievalResult(
            tool_name=self.name,
            answer=f"I could not find course data for '{entity}' in the local index.",
            sources=[],
            confidence="low",
        )
