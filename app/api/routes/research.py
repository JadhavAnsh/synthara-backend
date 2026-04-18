from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.research import (
    CreateResearchJobRequest,
    ErrorResponse,
    ExportResponse,
    PaperDocument,
    ResearchJobResponse,
    SectionRegenerateRequest,
    StructuredKnowledge,
)
from app.services.research import ResearchService

router = APIRouter(prefix="/api/research", tags=["research"])


def get_research_service(request: Request) -> ResearchService:
    return request.app.state.research_service


ResearchServiceDep = Annotated[ResearchService, Depends(get_research_service)]


@router.post("/jobs", response_model=ResearchJobResponse)
async def create_research_job(
    payload: CreateResearchJobRequest,
    service: ResearchServiceDep,
) -> ResearchJobResponse:
    return await service.create_job(payload)


@router.get("/jobs/{job_id}", response_model=ResearchJobResponse)
async def get_research_job(job_id: str, service: ResearchServiceDep) -> ResearchJobResponse:
    job = service.get_job(job_id)
    if job is None:
        raise _not_found("job", job_id)
    return job


@router.get("/jobs/{job_id}/knowledge", response_model=StructuredKnowledge)
async def get_research_knowledge(job_id: str, service: ResearchServiceDep) -> StructuredKnowledge:
    knowledge = service.get_knowledge(job_id)
    if knowledge is None:
        raise _not_found("knowledge", job_id)
    return knowledge


@router.get("/jobs/{job_id}/document", response_model=PaperDocument)
async def get_research_document(job_id: str, service: ResearchServiceDep) -> PaperDocument:
    document = service.get_document(job_id)
    if document is None:
        raise _not_found("document", job_id)
    return document


@router.post("/jobs/{job_id}/sections/{section_id}/regenerate", response_model=PaperDocument)
async def regenerate_section(
    job_id: str,
    section_id: str,
    payload: SectionRegenerateRequest,
    service: ResearchServiceDep,
) -> PaperDocument:
    document = await service.regenerate_section(job_id, section_id, payload)
    if document is None:
        raise _not_found("document", job_id)
    return document


@router.post("/jobs/{job_id}/exports/markdown", response_model=ExportResponse)
async def export_job_markdown(job_id: str, service: ResearchServiceDep) -> ExportResponse:
    export = service.export_markdown(job_id)
    if export is None:
        raise _not_found("document", job_id)
    return export


def _not_found(kind: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ErrorResponse(error="not_found", message=f"{kind} for {identifier!r} was not found").model_dump(),
    )
