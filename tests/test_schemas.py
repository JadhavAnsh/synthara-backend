import pytest
from pydantic import ValidationError

from app.schemas.research import (
    CitationReference,
    ClaimRecord,
    CreateResearchJobRequest,
    EvidenceChunk,
    EvidenceSupportStatus,
    GenerationDepth,
    KeyPoint,
    PaperTemplateType,
    ResearchPlan,
    ResearchRound,
    SourceProvider,
    SourceRecord,
    StructuredKnowledge,
)


def test_create_research_job_request_defaults() -> None:
    request = CreateResearchJobRequest(topic=" retrieval augmented generation ")

    assert request.topic == "retrieval augmented generation"
    assert request.depth == GenerationDepth.ACADEMIC
    assert request.template == PaperTemplateType.IEEE


def test_invalid_depth_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateResearchJobRequest(topic="rag", depth="shallow")


def test_structured_knowledge_rejects_unknown_source_reference() -> None:
    source = SourceRecord(
        source_id="src_1",
        provider=SourceProvider.ARXIV,
        title="Grounded Generation",
        url="https://example.com/paper",
    )

    with pytest.raises(ValidationError):
        StructuredKnowledge(
            job_id="job_1",
            plan=ResearchPlan(
                topic="grounding",
                objective="Investigate grounding",
                depth=GenerationDepth.ACADEMIC,
                template=PaperTemplateType.IEEE,
                planned_rounds=1,
            ),
            rounds=[ResearchRound(round_index=1, query="grounding")],
            topics=["grounding"],
            key_points=[KeyPoint(claim="A grounded claim.", source_ids=["src_missing"])],
            claims=[
                ClaimRecord(
                    claim_id="claim_1",
                    claim="A grounded claim.",
                    source_ids=["src_1"],
                    chunk_ids=["chunk_1"],
                    support_status=EvidenceSupportStatus.SUPPORTED,
                )
            ],
            citations=[
                CitationReference(
                    source_id="src_1",
                    title="Grounded Generation",
                    url="https://example.com/paper",
                )
            ],
            raw_sources=[source],
            evidence_chunks=[
                EvidenceChunk(
                    chunk_id="chunk_1",
                    source_id="src_1",
                    text="A source-backed evidence chunk.",
                    relevance_score=1.0,
                )
            ],
        )
