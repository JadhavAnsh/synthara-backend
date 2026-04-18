import asyncio

from app.export.markdown import export_markdown
from app.repositories.research import InMemoryResearchRepository
from app.research.orchestrator import ResearchOrchestrator
from app.schemas.research import (
    CreateResearchJobRequest,
    ExportResponse,
    ExportType,
    PaperDocument,
    ResearchJobResponse,
    ResearchJobStatus,
    ResearchStage,
    SectionRegenerateRequest,
    StructuredKnowledge,
)
from app.utils.ids import new_job_id


class ResearchService:
    def __init__(self, repository: InMemoryResearchRepository, orchestrator: ResearchOrchestrator) -> None:
        self._repository = repository
        self._orchestrator = orchestrator
        self._tasks: set[asyncio.Task] = set()

    async def create_job(self, request: CreateResearchJobRequest) -> ResearchJobResponse:
        job = self._repository.create_job(new_job_id(), request)
        self._repository.update_job(
            job.job_id,
            status=ResearchJobStatus.QUEUED,
            stage=ResearchStage.QUEUED,
            progress=0.0,
        )
        self._repository.append_activity(job.job_id, ResearchStage.QUEUED, "job queued")
        task = asyncio.create_task(self._orchestrator.run_job(job.job_id, request))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return self.get_job(job.job_id)

    def get_job(self, job_id: str) -> ResearchJobResponse | None:
        job = self._repository.get_job(job_id)
        if job is None:
            return None
        return job.to_response()

    def get_knowledge(self, job_id: str) -> StructuredKnowledge | None:
        return self._repository.get_knowledge(job_id)

    def get_document(self, job_id: str) -> PaperDocument | None:
        return self._repository.get_document(job_id)

    async def regenerate_section(self, job_id: str, section_id: str, payload: SectionRegenerateRequest) -> PaperDocument | None:
        return await self._orchestrator.regenerate_section(job_id, section_id, payload.instructions)

    def export_markdown(self, job_id: str) -> ExportResponse | None:
        cached = self._repository.get_export(job_id, ExportType.MARKDOWN)
        if cached is not None:
            return cached
        document = self._repository.get_document(job_id)
        if document is None:
            return None
        exported = export_markdown(document)
        self._repository.save_export(exported)
        return exported
