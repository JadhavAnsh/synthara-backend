from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from email.utils import parsedate_to_datetime
import random
import time
from xml.etree import ElementTree

import httpx

from app.schemas.research import SourceCandidate, SourceProvider, SourceType


class ProviderError(Exception):
    category = "provider_error"

    def __init__(self, provider: SourceProvider, message: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.message = message


class ProviderRequestError(ProviderError):
    def __init__(
        self,
        provider: SourceProvider,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        auth_related: bool = False,
    ) -> None:
        super().__init__(provider, message)
        self.status_code = status_code
        self.retryable = retryable
        self.auth_related = auth_related
        self.category = _failure_category_for_status(status_code, retryable, auth_related)


class ProviderUnavailableError(ProviderError):
    category = "provider_unavailable"


class SourceProviderClient(ABC):
    provider: SourceProvider
    capabilities: frozenset[str] = frozenset({"search"})

    @abstractmethod
    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        raise NotImplementedError


class ArxivProviderClient(SourceProviderClient):
    provider = SourceProvider.ARXIV
    capabilities = frozenset({"search"})

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        base_url: str = "https://export.arxiv.org/api/query",
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        response = await request_with_retries(
            self.provider,
            lambda: self._http_client.get(
                self._base_url,
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": limit,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            ),
            max_retries=self._max_retries,
            backoff_seconds=self._backoff_seconds,
            sleep=self._sleep,
        )
        return parse_arxiv_response(response.text, query=query, round_index=round_index)


class TavilyProviderClient(SourceProviderClient):
    provider = SourceProvider.WEB
    capabilities = frozenset({"search", "content"})

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_key: str | None,
        endpoint: str = "https://api.tavily.com/search",
        search_depth: str = "basic",
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key
        self._endpoint = endpoint
        self._search_depth = search_depth
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        if not self._api_key:
            raise ProviderUnavailableError(self.provider, "Tavily API key is not configured")

        response = await request_with_retries(
            self.provider,
            lambda: self._http_client.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "max_results": limit,
                    "search_depth": self._search_depth,
                    "include_answer": False,
                    "include_raw_content": True,
                },
            ),
            max_retries=self._max_retries,
            backoff_seconds=self._backoff_seconds,
            sleep=self._sleep,
        )
        return parse_tavily_response(response.json(), query=query, round_index=round_index)


class AlphaXivProviderClient(SourceProviderClient):
    provider = SourceProvider.ALPHAXIV
    capabilities = frozenset({"search", "full_text", "qa", "code"})

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        base_url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    async def auth_status(self) -> dict:
        response = await request_with_retries(
            self.provider,
            lambda: self._http_client.get(f"{self._base_url}/auth/status", timeout=self._timeout_seconds),
            max_retries=self._max_retries,
            backoff_seconds=self._backoff_seconds,
            sleep=self._sleep,
        )
        return response.json()

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        response = await request_with_retries(
            self.provider,
            lambda: self._http_client.post(
                f"{self._base_url}/papers/search",
                json={"query": query, "limit": limit, "mode": "semantic"},
                timeout=self._timeout_seconds,
            ),
            max_retries=self._max_retries,
            backoff_seconds=self._backoff_seconds,
            sleep=self._sleep,
        )
        return parse_alphaxiv_search_response(response.json(), query=query, round_index=round_index)

    async def get_paper(self, paper: str, *, full_text: bool = True) -> dict:
        response = await request_with_retries(
            self.provider,
            lambda: self._http_client.post(
                f"{self._base_url}/papers/get",
                json={"paper": paper, "full_text": full_text},
                timeout=self._timeout_seconds,
            ),
            max_retries=self._max_retries,
            backoff_seconds=self._backoff_seconds,
            sleep=self._sleep,
        )
        return response.json()


async def request_with_retries(
    provider: SourceProvider,
    request: Callable[[], Awaitable[httpx.Response]],
    *,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    attempt = 0
    last_error: ProviderRequestError | None = None
    while attempt <= max_retries:
        started_at = time.perf_counter()
        try:
            response = await request()
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = _is_retryable_status(status_code)
            auth_related = status_code in {401, 403}
            last_error = ProviderRequestError(
                provider,
                _safe_http_error_message(provider, status_code),
                status_code=status_code,
                retryable=retryable,
                auth_related=auth_related,
            )
            if not retryable or attempt >= max_retries:
                raise last_error from exc
            delay = _retry_delay(exc.response, attempt, backoff_seconds)
        except httpx.TimeoutException as exc:
            last_error = ProviderRequestError(provider, f"{provider.value} request timed out", retryable=True)
            if attempt >= max_retries:
                raise last_error from exc
            delay = _jittered_backoff(attempt, backoff_seconds)
        except httpx.RequestError as exc:
            last_error = ProviderRequestError(provider, f"{provider.value} request failed", retryable=True)
            if attempt >= max_retries:
                raise last_error from exc
            delay = _jittered_backoff(attempt, backoff_seconds)

        elapsed = time.perf_counter() - started_at
        await sleep(max(0.0, delay - elapsed))
        attempt += 1

    if last_error is not None:
        raise last_error
    raise ProviderRequestError(provider, f"{provider.value} request failed")


def parse_arxiv_response(xml_text: str, *, query: str = "", round_index: int = 1) -> list[SourceCandidate]:
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    root = ElementTree.fromstring(xml_text)
    candidates: list[SourceCandidate] = []
    for entry in root.findall("atom:entry", namespace):
        title = entry.findtext("atom:title", default="", namespaces=namespace)
        url = entry.findtext("atom:id", default="", namespaces=namespace)
        summary = entry.findtext("atom:summary", default="", namespaces=namespace)
        published = entry.findtext("atom:published", default="", namespaces=namespace)
        authors = [
            author.findtext("atom:name", default="", namespaces=namespace).strip()
            for author in entry.findall("atom:author", namespace)
        ]
        authors = [author for author in authors if author]
        year = _year_from_date(published)
        if title.strip() and url.strip():
            candidates.append(
                SourceCandidate(
                    provider=SourceProvider.ARXIV,
                    source_type=SourceType.ACADEMIC,
                    title=title,
                    url=url,
                    authors=authors,
                    year=year,
                    abstract=summary,
                    discovery_query=query,
                    discovery_round=round_index,
                    metadata={"published": published, "source_type": "academic"},
                )
            )
    return candidates


def parse_tavily_response(payload: dict, *, query: str = "", round_index: int = 1) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    request_id = payload.get("request_id")
    for item in payload.get("results", []):
        title = item.get("title") or ""
        url = item.get("url") or ""
        raw_content = item.get("raw_content") or ""
        content = raw_content or item.get("content") or ""
        abstract = item.get("content") or raw_content
        if title.strip() and url:
            candidates.append(
                SourceCandidate(
                    provider=SourceProvider.WEB,
                    source_type=SourceType.WEB,
                    title=title,
                    url=url,
                    authors=[],
                    abstract=abstract,
                    content=content,
                    discovery_query=query,
                    discovery_round=round_index,
                    score=item.get("score"),
                    metadata={
                        "score": item.get("score"),
                        "source": "tavily",
                        "source_type": "web",
                        "request_id": request_id,
                        "favicon": item.get("favicon"),
                        "evidence_origin": "raw_content" if raw_content else "snippet",
                    },
                )
            )
    return candidates


def parse_alphaxiv_search_response(payload: dict, *, query: str = "", round_index: int = 1) -> list[SourceCandidate]:
    if isinstance(payload, list):
        results = payload
    elif isinstance(payload, dict):
        results = payload.get("results") or payload.get("papers") or []
    else:
        results = []
    candidates: list[SourceCandidate] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        url = item.get("url") or item.get("paperUrl") or item.get("id") or ""
        if not title.strip() or not url:
            continue
        authors_raw = item.get("authors", [])
        if not isinstance(authors_raw, list):
            authors_raw = []
        authors = [author.get("name", "").strip() if isinstance(author, dict) else str(author).strip() for author in authors_raw]
        authors = [author for author in authors if author]
        candidates.append(
            SourceCandidate(
                provider=SourceProvider.ALPHAXIV,
                source_type=SourceType.ACADEMIC,
                title=title,
                url=url,
                authors=authors,
                year=item.get("year"),
                abstract=item.get("summary") or item.get("abstract") or "",
                content=item.get("fullText") or item.get("content") or "",
                discovery_query=query,
                discovery_round=round_index,
                score=item.get("score"),
                metadata={"source": "alphaxiv", "raw": item},
            )
        )
    return candidates


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def _failure_category_for_status(status_code: int | None, retryable: bool, auth_related: bool) -> str:
    if auth_related:
        return "provider_auth"
    if status_code == 429:
        return "provider_rate_limited"
    if retryable:
        return "provider_transient"
    return "provider_error"


def _safe_http_error_message(provider: SourceProvider, status_code: int) -> str:
    if status_code in {401, 403}:
        return f"{provider.value} request was refused with HTTP {status_code}"
    if status_code == 429:
        return f"{provider.value} request was rate limited with HTTP 429"
    return f"{provider.value} request failed with HTTP {status_code}"


def _retry_delay(response: httpx.Response, attempt: int, backoff_seconds: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        parsed = _parse_retry_after(retry_after)
        if parsed is not None:
            return parsed
    return _jittered_backoff(attempt, backoff_seconds)


def _parse_retry_after(value: str) -> float | None:
    if value.isdigit():
        return float(value)
    try:
        retry_at = parsedate_to_datetime(value)
        return max(0.0, (retry_at - datetime.now(retry_at.tzinfo)).total_seconds())
    except (TypeError, ValueError):
        return None


def _jittered_backoff(attempt: int, backoff_seconds: float) -> float:
    if backoff_seconds == 0:
        return 0.0
    return backoff_seconds * (2**attempt) + random.uniform(0, backoff_seconds / 2)


def _year_from_date(value: str) -> int | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).year
    except ValueError:
        return None
