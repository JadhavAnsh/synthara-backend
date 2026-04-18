from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class ResearchJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStage(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    VERIFYING = "verifying"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceProvider(StrEnum):
    ALPHAXIV = "alphaxiv"
    ARXIV = "arxiv"
    WEB = "web"


class SourceType(StrEnum):
    ACADEMIC = "academic"
    WEB = "web"
    CODE = "code"
    DOCS = "docs"


class EvidenceSupportStatus(StrEnum):
    SUPPORTED = "supported"
    WEAK = "weak"
    REJECTED = "rejected"


class GenerationDepth(StrEnum):
    BASIC = "basic"
    ACADEMIC = "academic"
    DEEP = "deep"


class CitationStyle(StrEnum):
    NUMERIC = "numeric"
    AUTHOR_YEAR = "author_year"


class PaperTemplateType(StrEnum):
    IEEE = "IEEE"
    HARVARD = "Harvard"


class ExportType(StrEnum):
    MARKDOWN = "markdown"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateResearchJobRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "topic": "retrieval augmented generation for citation-grounded academic writing",
                    "description": "Focus on source traceability, citation accuracy, and editable paper generation.",
                    "depth": "academic",
                    "template": "IEEE",
                    "max_sources": 9,
                    "max_iterations": 2,
                }
            ]
        }
    )

    topic: str = Field(min_length=1, max_length=500)
    description: str = Field(default="")
    depth: GenerationDepth = Field(default=GenerationDepth.ACADEMIC)
    template: PaperTemplateType = Field(default=PaperTemplateType.IEEE)
    max_sources: int = Field(default=9, ge=1, le=30)
    max_iterations: int = Field(default=2, ge=1, le=5)

    @field_validator("topic", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def topic_must_not_be_blank(self) -> "CreateResearchJobRequest":
        if not self.topic:
            raise ValueError("topic must not be blank")
        return self


class ResearchQuery(BaseModel):
    query: str = Field(min_length=1)
    rationale: str = Field(default="")


class ResearchPlan(BaseModel):
    topic: str
    objective: str
    depth: GenerationDepth
    template: PaperTemplateType
    queries: list[ResearchQuery] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    planned_rounds: int = Field(default=1, ge=1)


class SourceCandidate(BaseModel):
    provider: SourceProvider
    source_type: SourceType = Field(default=SourceType.ACADEMIC)
    title: str = Field(min_length=1)
    url: HttpUrl
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str = Field(default="")
    content: str = Field(default="")
    discovery_query: str = Field(default="")
    discovery_round: int = Field(default=1, ge=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "abstract", "content", "discovery_query")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return " ".join(value.split())


class SourceRecord(BaseModel):
    source_id: str
    provider: SourceProvider
    source_type: SourceType = Field(default=SourceType.ACADEMIC)
    title: str
    url: HttpUrl
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str = Field(default="")
    content: str = Field(default="")
    discovery_query: str = Field(default="")
    discovery_round: int = Field(default=1, ge=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RejectedSource(BaseModel):
    source: SourceRecord
    reason: str


class EvidenceChunk(BaseModel):
    chunk_id: str
    source_id: str
    text: str = Field(min_length=1)
    relevance_score: float = Field(ge=0.0, le=1.0)
    claims: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def claims_must_have_text(self) -> "EvidenceChunk":
        self.claims = [claim for claim in self.claims if claim.strip()]
        return self


class ClaimRecord(BaseModel):
    claim_id: str
    claim: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    chunk_ids: list[str] = Field(default_factory=list)
    support_status: EvidenceSupportStatus
    notes: str = Field(default="")


class KeyPoint(BaseModel):
    claim: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class CitationReference(BaseModel):
    source_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    url: HttpUrl


class ResearchRound(BaseModel):
    round_index: int = Field(ge=1)
    query: str
    provider_results: dict[SourceProvider, int] = Field(default_factory=dict)
    accepted_source_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParagraphProvenance(BaseModel):
    paragraph_id: str
    text: str
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)


class StructuredKnowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    plan: ResearchPlan
    rounds: list[ResearchRound] = Field(default_factory=list)
    topics: list[str]
    key_points: list[KeyPoint]
    claims: list[ClaimRecord] = Field(default_factory=list)
    citations: list[CitationReference]
    raw_sources: list[SourceRecord]
    rejected_sources: list[RejectedSource] = Field(default_factory=list)
    evidence_chunks: list[EvidenceChunk]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_source_references(self) -> "StructuredKnowledge":
        source_ids = {source.source_id for source in self.raw_sources}
        for key_point in self.key_points:
            missing = set(key_point.source_ids) - source_ids
            if missing:
                raise ValueError(f"key point references unknown source IDs: {sorted(missing)}")
        for claim in self.claims:
            missing = set(claim.source_ids) - source_ids
            if missing:
                raise ValueError(f"claim references unknown source IDs: {sorted(missing)}")
        for chunk in self.evidence_chunks:
            if chunk.source_id not in source_ids:
                raise ValueError(f"evidence chunk references unknown source ID: {chunk.source_id}")
        citation_ids = {citation.source_id for citation in self.citations}
        missing_citations = citation_ids - source_ids
        if missing_citations:
            raise ValueError(f"citation references unknown source IDs: {sorted(missing_citations)}")
        return self


class PaperSection(BaseModel):
    section_id: str
    heading: str
    order: int = Field(ge=0)
    content: str = Field(default="")
    citation_source_ids: list[str] = Field(default_factory=list)
    provenance: list[ParagraphProvenance] = Field(default_factory=list)


class PaperDocument(BaseModel):
    job_id: str
    title: str
    template: PaperTemplateType
    depth: GenerationDepth
    sections: list[PaperSection]
    references: list[CitationReference]
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SectionRegenerateRequest(BaseModel):
    instructions: str = Field(default="")

    @field_validator("instructions")
    @classmethod
    def trim_instructions(cls, value: str) -> str:
        return value.strip()


class ExportResponse(BaseModel):
    job_id: str
    export_type: ExportType
    content: str
    media_type: str
    created_at: datetime = Field(default_factory=utc_now)


class JobActivityEntry(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    stage: ResearchStage
    message: str


class ResearchJobResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "job_7b3f1f5b4e4c40e1a2e29d7f5d4d9c8b",
                    "status": "running",
                    "stage": "researching",
                    "topic": "retrieval augmented generation for citation-grounded academic writing",
                    "depth": "academic",
                    "template": "IEEE",
                    "progress": 0.35,
                    "created_at": "2026-04-16T07:30:00Z",
                    "updated_at": "2026-04-16T07:30:03Z",
                    "failure_category": None,
                    "failure_message": None,
                    "provider_failures": {},
                    "warnings": ["alphaxiv bridge unavailable; using arXiv fallback"],
                    "activity": [
                        {"timestamp": "2026-04-16T07:30:00Z", "stage": "planning", "message": "planning research"}
                    ],
                }
            ]
        }
    )

    job_id: str
    status: ResearchJobStatus
    stage: ResearchStage
    topic: str
    depth: GenerationDepth
    template: PaperTemplateType
    progress: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime
    failure_category: str | None = None
    failure_message: str | None = None
    provider_failures: dict[SourceProvider, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    activity: list[JobActivityEntry] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    message: str
