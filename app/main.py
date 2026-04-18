from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI

from app.api.routes import health_router, research_router, root_router
from app.paper.generator import GeminiClient, PaperDocumentGenerator
from app.repositories.research import InMemoryResearchRepository
from app.research.orchestrator import ResearchOrchestrator
from app.research.providers import AlphaXivProviderClient, ArxivProviderClient, TavilyProviderClient
from app.services.research import ResearchService
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    timeout = httpx.Timeout(settings.provider_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
        repository = InMemoryResearchRepository()
        providers = [
            AlphaXivProviderClient(
                http_client,
                base_url=settings.alphaxiv_bridge_url,
                timeout_seconds=settings.alphaxiv_bridge_timeout_seconds,
                max_retries=settings.provider_max_retries,
                backoff_seconds=settings.provider_backoff_seconds,
            ),
            ArxivProviderClient(
                http_client,
                max_retries=settings.provider_max_retries,
                backoff_seconds=settings.provider_backoff_seconds,
            ),
            TavilyProviderClient(
                http_client,
                api_key=settings.tavily_api_key,
                endpoint=settings.tavily_search_endpoint,
                search_depth=settings.tavily_search_depth,
                max_retries=settings.provider_max_retries,
                backoff_seconds=settings.provider_backoff_seconds,
            ),
        ]
        gemini_client = GeminiClient(
            http_client=http_client,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            endpoint_template=settings.gemini_api_endpoint,
            temperature=settings.gemini_temperature,
        )
        document_generator = PaperDocumentGenerator(gemini_client)
        orchestrator = ResearchOrchestrator(
            repository,
            providers,
            document_generator,
            max_sources_per_provider=settings.max_sources_per_provider,
            min_accepted_sources=settings.min_accepted_sources,
        )
        app.state.research_service = ResearchService(repository, orchestrator)
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Synthara Research Backend",
        version="0.2.0",
        summary="Source-grounded autonomous research API for Synthara Research Studio.",
        description=(
            "Synthara's Python backend owns autonomous source discovery, research planning, "
            "structured knowledge assembly, section drafting, citation resolution, and export preparation."
        ),
        lifespan=lifespan,
    )
    app.include_router(root_router)
    app.include_router(health_router)
    app.include_router(research_router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
