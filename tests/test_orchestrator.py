import pytest

from app.paper.generator import GeminiClient, PaperDocumentGenerator
from app.repositories.research import InMemoryResearchRepository
from app.research.orchestrator import ResearchOrchestrator
from app.schemas.research import CreateResearchJobRequest, ResearchJobStatus, ResearchStage, SourceCandidate, SourceProvider


class FakeProvider:
    def __init__(self, provider: SourceProvider, candidates: list[SourceCandidate] | None = None) -> None:
        self.provider = provider
        self.candidates = candidates or []
        self.calls: list[tuple[str, int, int]] = []

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        self.calls.append((query, limit, round_index))
        return self.candidates[:limit]


class FailingProvider:
    provider = SourceProvider.WEB

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        raise RuntimeError("provider failed")


class SequencedProvider:
    def __init__(self, provider: SourceProvider, batches: list[list[SourceCandidate]]) -> None:
        self.provider = provider
        self.batches = batches
        self.calls: list[tuple[str, int, int]] = []

    async def search(self, query: str, limit: int, *, round_index: int = 1) -> list[SourceCandidate]:
        self.calls.append((query, limit, round_index))
        index = min(len(self.calls) - 1, len(self.batches) - 1)
        return self.batches[index][:limit]


def candidate(
    url: str = "https://example.com/paper",
    provider: SourceProvider = SourceProvider.ARXIV,
) -> SourceCandidate:
    return SourceCandidate(
        provider=provider,
        title="Grounded Research",
        url=url,
        abstract="Grounded research systems connect claims to verifiable source records for downstream citation.",
    )


@pytest.mark.asyncio
async def test_orchestrator_happy_path_completes_job() -> None:
    repository = InMemoryResearchRepository()
    repository.create_job("job_1", CreateResearchJobRequest(topic="grounded research"))
    provider = FakeProvider(SourceProvider.ARXIV, [candidate()])
    orchestrator = ResearchOrchestrator(
        repository,
        [provider],
        PaperDocumentGenerator(GeminiClient(None, None, "gemini-2.5-flash", "", 0.2)),
        max_sources_per_provider=3,
    )

    await orchestrator.run_job("job_1", CreateResearchJobRequest(topic="grounded research"))

    response = repository.get_job("job_1").to_response()
    assert response.status == ResearchJobStatus.COMPLETED
    assert response.stage == ResearchStage.COMPLETED
    knowledge = repository.get_knowledge(response.job_id)
    document = repository.get_document(response.job_id)
    assert knowledge is not None
    assert document is not None
    assert document.sections[0].heading == "Abstract"


@pytest.mark.asyncio
async def test_orchestrator_records_partial_provider_failure() -> None:
    repository = InMemoryResearchRepository()
    repository.create_job("job_1", CreateResearchJobRequest(topic="grounded research"))
    orchestrator = ResearchOrchestrator(
        repository,
        [FakeProvider(SourceProvider.ARXIV, [candidate()]), FailingProvider()],
        PaperDocumentGenerator(GeminiClient(None, None, "gemini-2.5-flash", "", 0.2)),
        max_sources_per_provider=3,
    )

    await orchestrator.run_job("job_1", CreateResearchJobRequest(topic="grounded research"))

    response = repository.get_job("job_1").to_response()
    assert response.status == ResearchJobStatus.COMPLETED
    assert response.provider_failures[SourceProvider.WEB] == "provider failed"


@pytest.mark.asyncio
async def test_orchestrator_fails_when_evidence_is_below_threshold() -> None:
    repository = InMemoryResearchRepository()
    repository.create_job("job_1", CreateResearchJobRequest(topic="grounded research"))
    orchestrator = ResearchOrchestrator(
        repository,
        [FakeProvider(SourceProvider.ARXIV, [candidate()])],
        PaperDocumentGenerator(GeminiClient(None, None, "gemini-2.5-flash", "", 0.2)),
        max_sources_per_provider=3,
        min_accepted_sources=2,
    )

    await orchestrator.run_job("job_1", CreateResearchJobRequest(topic="grounded research"))

    response = repository.get_job("job_1").to_response()
    assert response.status == ResearchJobStatus.FAILED
    assert response.failure_category == "research_failed"
    assert "insufficient evidence" in response.failure_message


@pytest.mark.asyncio
async def test_orchestrator_runs_query_variants_until_threshold_is_met() -> None:
    repository = InMemoryResearchRepository()
    repository.create_job("job_1", CreateResearchJobRequest(topic="grounded research"))
    provider = SequencedProvider(
        SourceProvider.ARXIV,
        [
            [candidate("https://example.com/one")],
            [candidate("https://example.com/two")],
        ],
    )
    orchestrator = ResearchOrchestrator(
        repository,
        [provider],
        PaperDocumentGenerator(GeminiClient(None, None, "gemini-2.5-flash", "", 0.2)),
        max_sources_per_provider=3,
        min_accepted_sources=2,
    )

    await orchestrator.run_job("job_1", CreateResearchJobRequest(topic="grounded research", max_sources=3, max_iterations=2))

    response = repository.get_job("job_1").to_response()
    assert response.status == ResearchJobStatus.COMPLETED
    assert provider.calls == [("grounded research", 3, 1), ("grounded research survey", 3, 2)]


@pytest.mark.asyncio
async def test_orchestrator_degrades_when_gemini_times_out() -> None:
    class TimeoutHttpClient:
        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("timed out")

    import httpx

    repository = InMemoryResearchRepository()
    repository.create_job("job_1", CreateResearchJobRequest(topic="grounded research"))
    provider = FakeProvider(SourceProvider.ARXIV, [candidate()])
    orchestrator = ResearchOrchestrator(
        repository,
        [provider],
        PaperDocumentGenerator(
            GeminiClient(TimeoutHttpClient(), "gemini-key", "gemini-2.5-flash", "https://example.com/{model}", 0.2)
        ),
        max_sources_per_provider=3,
    )

    await orchestrator.run_job("job_1", CreateResearchJobRequest(topic="grounded research"))

    response = repository.get_job("job_1").to_response()
    document = repository.get_document("job_1")
    assert response.status == ResearchJobStatus.COMPLETED
    assert document is not None
    assert document.sections[0].content
