import asyncio

import httpx
import pytest

from app.main import create_app
from app.paper.generator import GeminiClient, PaperDocumentGenerator
from app.repositories.research import InMemoryResearchRepository
from app.research.orchestrator import ResearchOrchestrator
from app.schemas.research import SourceCandidate, SourceProvider
from app.services.research import ResearchService


class FakeProvider:
    provider = SourceProvider.ARXIV

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        return [
            SourceCandidate(
                provider=SourceProvider.ARXIV,
                title="Grounded Research",
                url="https://example.com/paper",
                abstract="Grounded research systems connect claims to verifiable source records for downstream citation.",
            )
        ]


@pytest.fixture
def app_with_fake_service():
    app = create_app()
    repository = InMemoryResearchRepository()
    orchestrator = ResearchOrchestrator(
        repository,
        [FakeProvider()],
        PaperDocumentGenerator(GeminiClient(None, None, "gemini-2.5-flash", "", 0.2)),
        max_sources_per_provider=3,
    )
    app.state.research_service = ResearchService(repository, orchestrator)
    return app


async def wait_for_completion(client: httpx.AsyncClient, job_id: str) -> dict:
    for _ in range(20):
        response = await client.get(f"/api/research/jobs/{job_id}")
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        await asyncio.sleep(0.01)
    raise AssertionError("job did not complete in time")


@pytest.mark.asyncio
async def test_create_job_and_get_knowledge_document_and_export(app_with_fake_service) -> None:
    transport = httpx.ASGITransport(app=app_with_fake_service)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post("/api/research/jobs", json={"topic": "grounded research"})
        assert create_response.status_code == 200
        job = create_response.json()
        assert job["status"] in {"queued", "running"}

        completed_job = await wait_for_completion(client, job["job_id"])
        assert completed_job["status"] == "completed"

        knowledge_response = await client.get(f"/api/research/jobs/{job['job_id']}/knowledge")
        assert knowledge_response.status_code == 200
        assert knowledge_response.json()["raw_sources"][0]["title"] == "Grounded Research"

        document_response = await client.get(f"/api/research/jobs/{job['job_id']}/document")
        assert document_response.status_code == 200
        assert document_response.json()["sections"][0]["heading"] == "Abstract"

        regenerate_response = await client.post(
            f"/api/research/jobs/{job['job_id']}/sections/introduction/regenerate",
            json={"instructions": "Focus on motivation."},
        )
        assert regenerate_response.status_code == 200
        assert regenerate_response.json()["sections"][1]["section_id"] == "introduction"

        export_response = await client.post(f"/api/research/jobs/{job['job_id']}/exports/markdown")
        assert export_response.status_code == 200
        assert export_response.json()["media_type"] == "text/markdown"
        assert "# Grounded Research" in export_response.json()["content"]


@pytest.mark.asyncio
async def test_unknown_job_returns_not_found(app_with_fake_service) -> None:
    transport = httpx.ASGITransport(app=app_with_fake_service)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/research/jobs/job_missing")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "not_found"
