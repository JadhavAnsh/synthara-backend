import re

from app.schemas.research import (
    CitationReference,
    ClaimRecord,
    EvidenceChunk,
    EvidenceSupportStatus,
    KeyPoint,
    ResearchPlan,
    ResearchRound,
    SourceRecord,
    StructuredKnowledge,
)
from app.utils.ids import stable_id


def build_structured_knowledge(
    job_id: str,
    topic: str,
    plan: ResearchPlan,
    rounds: list[ResearchRound],
    sources: list[SourceRecord],
    rejected_sources,
    warnings: list[str],
) -> StructuredKnowledge:
    chunks: list[EvidenceChunk] = []
    key_points: list[KeyPoint] = []
    claims: list[ClaimRecord] = []
    citations: list[CitationReference] = []

    for source in sources:
        extracted_claims = extract_claims(source.content or source.abstract)
        if not extracted_claims:
            continue
        chunk_text = " ".join(extracted_claims[:3])
        chunk_id = stable_id("chunk", f"{source.source_id}:{chunk_text}")
        chunks.append(
            EvidenceChunk(
                chunk_id=chunk_id,
                source_id=source.source_id,
                text=chunk_text,
                relevance_score=1.0,
                claims=extracted_claims[:3],
            )
        )
        for claim_text in extracted_claims[:2]:
            status = EvidenceSupportStatus.SUPPORTED if len(claim_text) >= 60 else EvidenceSupportStatus.WEAK
            claim_id = stable_id("claim", f"{source.source_id}:{claim_text}")
            claims.append(
                ClaimRecord(
                    claim_id=claim_id,
                    claim=claim_text,
                    source_ids=[source.source_id],
                    chunk_ids=[chunk_id],
                    support_status=status,
                    notes="" if status == EvidenceSupportStatus.SUPPORTED else "short evidence span",
                )
            )
            if status != EvidenceSupportStatus.REJECTED:
                key_points.append(KeyPoint(claim=claim_text, source_ids=[source.source_id]))
        citations.append(
            CitationReference(
                source_id=source.source_id,
                title=source.title,
                authors=source.authors,
                year=source.year,
                url=source.url,
            )
        )

    return StructuredKnowledge(
        job_id=job_id,
        plan=plan,
        rounds=rounds,
        topics=extract_topics(topic),
        key_points=key_points,
        claims=claims,
        citations=citations,
        raw_sources=sources,
        rejected_sources=rejected_sources,
        evidence_chunks=chunks,
        warnings=warnings,
    )


def extract_claims(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    claims = [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 40]
    if claims:
        return claims
    return [normalized] if len(normalized) >= 20 else []


def extract_topics(topic: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", topic.strip())
    if not cleaned:
        return []
    parts = [part.strip(" ,.;:") for part in re.split(r"\band\b|,|/", cleaned, flags=re.IGNORECASE)]
    return [part for part in parts if part]
