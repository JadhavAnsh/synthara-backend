from app.knowledge.extraction import build_structured_knowledge, extract_claims
from app.research.normalization import normalize_sources
from app.schemas.research import (
    GenerationDepth,
    PaperTemplateType,
    ResearchPlan,
    ResearchQuery,
    ResearchRound,
    SourceCandidate,
    SourceProvider,
    SourceType,
)


def test_normalize_sources_deduplicates_by_url() -> None:
    candidates = [
        SourceCandidate(
            provider=SourceProvider.ARXIV,
            source_type=SourceType.ACADEMIC,
            title="First",
            url="https://example.com/paper",
            abstract="This source explains the first claim in enough detail.",
        ),
        SourceCandidate(
            provider=SourceProvider.ALPHAXIV,
            source_type=SourceType.ACADEMIC,
            title="Duplicate",
            url="https://example.com/paper",
            abstract="This duplicate should be skipped.",
        ),
    ]

    records, rejected = normalize_sources(candidates, max_sources=10)

    assert len(records) == 1
    assert records[0].provider == SourceProvider.ARXIV
    assert records[0].source_id.startswith("src_")
    assert rejected[0].reason == "duplicate"


def test_normalize_sources_deduplicates_by_doi() -> None:
    candidates = [
        SourceCandidate(
            provider=SourceProvider.ALPHAXIV,
            title="First DOI",
            url="https://example.com/one",
            abstract="This source explains the first claim in enough detail.",
            metadata={"external_ids": {"DOI": "10.1000/example"}},
        ),
        SourceCandidate(
            provider=SourceProvider.ARXIV,
            title="Duplicate DOI",
            url="https://example.com/two",
            abstract="This duplicate should be skipped.",
            metadata={"external_ids": {"DOI": "10.1000/EXAMPLE"}},
        ),
    ]

    records, _ = normalize_sources(candidates, max_sources=10)

    assert len(records) == 1
    assert records[0].title == "First DOI"


def test_extract_claims_uses_sentence_boundaries() -> None:
    claims = extract_claims(
        "Short. Retrieval augmented generation improves factual grounding when retrieved evidence is relevant. "
        "Citation systems need stable source identifiers."
    )

    assert claims == [
        "Retrieval augmented generation improves factual grounding when retrieved evidence is relevant.",
        "Citation systems need stable source identifiers.",
    ]


def test_build_structured_knowledge_links_evidence_to_sources() -> None:
    source = normalize_sources(
        [
            SourceCandidate(
                provider=SourceProvider.ARXIV,
                title="Grounded Generation",
                url="https://example.com/paper",
                authors=["Jane Doe"],
                year=2024,
                abstract="Retrieval augmented generation improves factual grounding when retrieved evidence is relevant.",
            )
        ],
        max_sources=1,
    )[0][0]

    knowledge = build_structured_knowledge(
        "job_1",
        "RAG and citations",
        ResearchPlan(
            topic="RAG and citations",
            objective="Investigate grounding",
            depth=GenerationDepth.ACADEMIC,
            template=PaperTemplateType.IEEE,
            queries=[ResearchQuery(query="rag and citations")],
            planned_rounds=1,
        ),
        [ResearchRound(round_index=1, query="rag and citations")],
        [source],
        [],
        [],
    )

    assert knowledge.topics == ["RAG", "citations"]
    assert knowledge.key_points[0].source_ids == [source.source_id]
    assert knowledge.evidence_chunks[0].source_id == source.source_id
    assert knowledge.citations[0].source_id == source.source_id
    assert knowledge.claims[0].chunk_ids
