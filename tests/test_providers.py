import httpx
import pytest

from app.research.providers import (
    AlphaXivProviderClient,
    ArxivProviderClient,
    ProviderError,
    ProviderRequestError,
    TavilyProviderClient,
    parse_alphaxiv_search_response,
    parse_arxiv_response,
    parse_tavily_response,
)
from app.schemas.research import SourceProvider


def test_parse_arxiv_response() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://arxiv.org/abs/2401.00001</id>
        <title> Grounded Research Systems </title>
        <summary> This paper studies grounded research systems with citation-aware generation. </summary>
        <published>2024-01-02T00:00:00Z</published>
        <author><name>Jane Doe</name></author>
      </entry>
    </feed>
    """

    candidates = parse_arxiv_response(xml, query="grounded research", round_index=1)

    assert len(candidates) == 1
    assert candidates[0].provider == SourceProvider.ARXIV
    assert candidates[0].title == "Grounded Research Systems"
    assert candidates[0].year == 2024
    assert candidates[0].discovery_query == "grounded research"


def test_parse_alphaxiv_response() -> None:
    candidates = parse_alphaxiv_search_response(
        {
            "results": [
                {
                    "title": "Citation Grounding",
                    "url": "https://alphaxiv.org/abs/2401.00001",
                    "authors": [{"name": "Jane Doe"}],
                    "year": 2025,
                    "abstract": "Citation grounding connects generated claims to concrete sources.",
                    "score": 0.91,
                }
            ]
        },
        query="citation grounding",
        round_index=2,
    )

    assert len(candidates) == 1
    assert candidates[0].provider == SourceProvider.ALPHAXIV
    assert candidates[0].score == 0.91
    assert candidates[0].discovery_round == 2


def test_parse_alphaxiv_response_skips_non_object_items() -> None:
    candidates = parse_alphaxiv_search_response(
        {
            "results": [
                "unexpected-string-item",
                {
                    "title": "Citation Grounding",
                    "url": "https://alphaxiv.org/abs/2401.00001",
                    "authors": "Jane Doe",
                },
            ]
        },
        query="citation grounding",
        round_index=1,
    )

    assert len(candidates) == 1
    assert candidates[0].title == "Citation Grounding"


def test_parse_tavily_response() -> None:
    candidates = parse_tavily_response(
        {
            "results": [
                {
                    "title": "RAG citation grounding",
                    "url": "https://example.com/rag-citations",
                    "content": "RAG systems need source-grounded evidence for citation-aware academic writing.",
                    "raw_content": "RAG systems need source-grounded evidence for citation-aware academic writing.",
                    "score": 0.92,
                    "favicon": "https://example.com/favicon.ico",
                }
            ]
        },
        query="rag citations",
        round_index=1,
    )

    assert len(candidates) == 1
    assert candidates[0].provider == SourceProvider.WEB
    assert candidates[0].title == "RAG citation grounding"
    assert candidates[0].metadata["source"] == "tavily"
    assert candidates[0].metadata["score"] == 0.92
    assert candidates[0].metadata["favicon"] == "https://example.com/favicon.ico"
    assert candidates[0].metadata["evidence_origin"] == "raw_content"


@pytest.mark.asyncio
async def test_arxiv_client_wraps_http_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ArxivProviderClient(client, base_url="https://example.com/arxiv", max_retries=0)
        with pytest.raises(ProviderError):
            await provider.search("rag", 1)


@pytest.mark.asyncio
async def test_tavily_client_posts_search_request() -> None:
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "RAG citations",
                        "url": "https://example.com/rag",
                        "content": "RAG citation grounding requires source-backed evidence.",
                    }
                ]
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TavilyProviderClient(
            client,
            api_key="tvly-test",
            endpoint="https://example.com/tavily",
            search_depth="advanced",
            max_retries=0,
        )
        candidates = await provider.search("rag citations", 2)

    assert captured_request is not None
    assert captured_request.method == "POST"
    assert captured_request.headers["Authorization"] == "Bearer tvly-test"
    assert b'"query":"rag citations"' in captured_request.content
    assert b'"max_results":2' in captured_request.content
    assert b'"search_depth":"advanced"' in captured_request.content
    assert candidates[0].title == "RAG citations"


@pytest.mark.asyncio
async def test_tavily_auth_failure_is_categorized() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TavilyProviderClient(
            client,
            api_key="bad-key",
            endpoint="https://example.com/tavily",
            max_retries=0,
        )
        with pytest.raises(ProviderRequestError) as exc_info:
            await provider.search("rag", 1)

    assert exc_info.value.status_code == 401
    assert exc_info.value.category == "provider_auth"


@pytest.mark.asyncio
async def test_alphaxiv_client_searches_bridge() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [{"title": "Alpha Paper", "url": "https://alphaxiv.org/abs/2401.1"}]},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AlphaXivProviderClient(client, base_url="https://example.com/bridge", max_retries=0)
        candidates = await provider.search("alpha paper", 2)

    assert candidates[0].provider == SourceProvider.ALPHAXIV
    assert candidates[0].title == "Alpha Paper"
