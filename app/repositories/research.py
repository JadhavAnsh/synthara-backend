from dataclasses import dataclass, field
from datetime import datetime

from app.schemas.research import (
    CreateResearchJobRequest,
    ExportResponse,
    JobActivityEntry,
    PaperDocument,
    ResearchJobResponse,
    ResearchJobStatus,
    ResearchStage,
    SourceProvider,
    StructuredKnowledge,
    utc_now,
)


@dataclass
class ResearchJobRecord:
    job_id: str
    request: CreateResearchJobRequest
    status: ResearchJobStatus = ResearchJobStatus.QUEUED
    stage: ResearchStage = ResearchStage.QUEUED
    progress: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    failure_category: str | None = None
    failure_message: str | None = None
    provider_failures: dict[SourceProvider, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    activity: list[JobActivityEntry] = field(default_factory=list)

    def to_response(self) -> ResearchJobResponse:
        return ResearchJobResponse(
            job_id=self.job_id,
            status=self.status,
            stage=self.stage,
            topic=self.request.topic,
            depth=self.request.depth,
            template=self.request.template,
            progress=self.progress,
            created_at=self.created_at,
            updated_at=self.updated_at,
            failure_category=self.failure_category,
            failure_message=self.failure_message,
            provider_failures=self.provider_failures,
            warnings=self.warnings,
            activity=self.activity,
        )


class InMemoryResearchRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJobRecord] = {}
        self._knowledge: dict[str, StructuredKnowledge] = {}
        self._documents: dict[str, PaperDocument] = {}
        self._exports: dict[tuple[str, str], ExportResponse] = {}

    def create_job(self, job_id: str, request: CreateResearchJobRequest) -> ResearchJobRecord:
        job = ResearchJobRecord(job_id=job_id, request=request)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> ResearchJobRecord | None:
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: ResearchJobStatus | None = None,
        stage: ResearchStage | None = None,
        progress: float | None = None,
        failure_category: str | None = None,
        failure_message: str | None = None,
        provider_failures: dict[SourceProvider, str] | None = None,
        warnings: list[str] | None = None,
    ) -> ResearchJobRecord:
        job = self._jobs[job_id]
        if status is not None:
            job.status = status
        if stage is not None:
            job.stage = stage
        if progress is not None:
            job.progress = progress
        if failure_category is not None:
            job.failure_category = failure_category
        if failure_message is not None:
            job.failure_message = failure_message
        if provider_failures is not None:
            job.provider_failures = provider_failures
        if warnings is not None:
            job.warnings = warnings
        job.updated_at = utc_now()
        return job

    def append_activity(self, job_id: str, stage: ResearchStage, message: str) -> ResearchJobRecord:
        job = self._jobs[job_id]
        job.activity.append(JobActivityEntry(stage=stage, message=message))
        job.updated_at = utc_now()
        return job

    def save_knowledge(self, knowledge: StructuredKnowledge) -> StructuredKnowledge:
        self._knowledge[knowledge.job_id] = knowledge
        return knowledge

    def get_knowledge(self, job_id: str) -> StructuredKnowledge | None:
        return self._knowledge.get(job_id)

    def save_document(self, document: PaperDocument) -> PaperDocument:
        self._documents[document.job_id] = document
        return document

    def get_document(self, job_id: str) -> PaperDocument | None:
        return self._documents.get(job_id)

    def save_export(self, export: ExportResponse) -> ExportResponse:
        self._exports[(export.job_id, export.export_type)] = export
        return export

    def get_export(self, job_id: str, export_type: str) -> ExportResponse | None:
        return self._exports.get((job_id, export_type))
