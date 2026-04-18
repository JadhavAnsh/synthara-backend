from __future__ import annotations

import asyncio
from collections.abc import Sequence
import re

from app.knowledge.extraction import build_structured_knowledge
from app.paper.generator import PaperDocumentGenerator
from app.repositories.research import InMemoryResearchRepository
from app.research.normalization import normalize_sources
from app.research.providers import AlphaXivProviderClient, ProviderError, SourceProviderClient
from app.schemas.research import (
    CreateResearchJobRequest,
    ResearchPlan,
    ResearchQuery,
    ResearchRound,
    ResearchStage,
    ResearchJobStatus,
    SourceCandidate,
    SourceProvider,
)


class ResearchOrchestrator:
    def __init__(
        self,
        repository: InMemoryResearchRepository,
        providers: Sequence[SourceProviderClient],
        document_generator: PaperDocumentGenerator,
        *,
        max_sources_per_provider: int,
        min_accepted_sources: int = 1,
    ) -> None:
        self._repository = repository
        self._providers = list(providers)
        self._document_generator = document_generator
        self._max_sources_per_provider = max_sources_per_provider
        self._min_accepted_sources = min_accepted_sources
        self._query_planner = ResearchQueryPlanner()

    async def run_job(self, job_id: str, request: CreateResearchJobRequest) -> None:
        provider_failures: dict[SourceProvider, str] = {}
        warnings: list[str] = []
        try:
            self._advance(job_id, ResearchStage.PLANNING, 0.05, "planning research")
            plan = self._query_planner.build_plan(request)

            self._advance(job_id, ResearchStage.RESEARCHING, 0.2, "running provider searches")
            candidates, rounds, provider_failures, warnings = await self._search(job_id, request, plan)
            sources, rejected_sources = normalize_sources(candidates, max_sources=request.max_sources)
            if len(sources) < self._min_accepted_sources:
                raise RuntimeError(
                    f"insufficient evidence: accepted {len(sources)} sources, required {self._min_accepted_sources}"
                )

            self._advance(job_id, ResearchStage.SYNTHESIZING, 0.55, "assembling structured knowledge")
            knowledge = build_structured_knowledge(
                job_id,
                request.topic,
                plan,
                rounds,
                sources,
                rejected_sources,
                warnings,
            )

            self._advance(job_id, ResearchStage.VERIFYING, 0.72, "verifying extracted claims")
            supported_claims = [claim for claim in knowledge.claims if claim.support_status != "rejected"]
            if len(supported_claims) < self._min_accepted_sources:
                raise RuntimeError(
                    f"insufficient extractable evidence: accepted {len(supported_claims)} claims, "
                    f"required {self._min_accepted_sources}"
                )

            self._repository.save_knowledge(knowledge)

            self._advance(job_id, ResearchStage.GENERATING, 0.88, "drafting initial paper sections")
            document = await self._document_generator.generate_document(knowledge)
            self._repository.save_document(document)

            self._repository.append_activity(job_id, ResearchStage.COMPLETED, "research job completed")
            self._repository.update_job(
                job_id,
                status=ResearchJobStatus.COMPLETED,
                stage=ResearchStage.COMPLETED,
                progress=1.0,
                provider_failures=provider_failures,
                warnings=warnings,
            )
        except Exception as exc:
            self._repository.append_activity(job_id, ResearchStage.FAILED, str(exc).strip() or "job failed")
            self._repository.update_job(
                job_id,
                status=ResearchJobStatus.FAILED,
                stage=ResearchStage.FAILED,
                progress=1.0,
                failure_category=_failure_category(exc),
                failure_message=_safe_failure_message(exc),
                provider_failures=provider_failures,
                warnings=warnings,
            )

    async def regenerate_section(self, job_id: str, section_id: str, instructions: str):
        knowledge = self._repository.get_knowledge(job_id)
        document = self._repository.get_document(job_id)
        if knowledge is None or document is None:
            return None
        if not any(section.section_id == section_id for section in document.sections):
            return None
        regenerated = await self._document_generator.regenerate_section(document, knowledge, section_id, instructions)
        self._repository.save_document(regenerated)
        self._repository.append_activity(job_id, ResearchStage.GENERATING, f"regenerated section {section_id}")
        return regenerated

    async def _search(
        self,
        job_id: str,
        request: CreateResearchJobRequest,
        plan: ResearchPlan,
    ) -> tuple[list[SourceCandidate], list[ResearchRound], dict[SourceProvider, str], list[str]]:
        provider_limit = min(self._max_sources_per_provider, request.max_sources)
        candidates: list[SourceCandidate] = []
        rounds: list[ResearchRound] = []
        provider_failures: dict[SourceProvider, str] = {}
        warnings: list[str] = []

        for round_index, planned_query in enumerate(plan.queries[: request.max_iterations], start=1):
            query = planned_query.query
            self._repository.append_activity(job_id, ResearchStage.RESEARCHING, f"search round {round_index}: {query}")
            results = await asyncio.gather(
                *(self._search_provider(provider, query, provider_limit, round_index) for provider in self._providers),
                return_exceptions=True,
            )
            provider_results: dict[SourceProvider, int] = {}
            for provider, result in zip(self._providers, results, strict=True):
                if isinstance(result, ProviderError):
                    provider_failures[provider.provider] = result.message
                    provider_results[provider.provider] = 0
                    if provider.provider == SourceProvider.ALPHAXIV:
                        warnings.append("alphaxiv unavailable; falling back to arXiv and Tavily")
                    continue
                if isinstance(result, Exception):
                    provider_failures[provider.provider] = _safe_failure_message(result)
                    provider_results[provider.provider] = 0
                    continue
                provider_results[provider.provider] = len(result)
                provider_failures.pop(provider.provider, None)
                candidates.extend(result)

            normalized_sources, _ = normalize_sources(candidates, max_sources=request.max_sources)
            rounds.append(
                ResearchRound(
                    round_index=round_index,
                    query=query,
                    provider_results=provider_results,
                    accepted_source_ids=[source.source_id for source in normalized_sources],
                    warnings=list(dict.fromkeys(warnings)),
                )
            )
            if len(normalized_sources) >= min(request.max_sources, self._min_accepted_sources):
                break

        return candidates, rounds, provider_failures, list(dict.fromkeys(warnings))

    async def _search_provider(
        self,
        provider: SourceProviderClient,
        query: str,
        limit: int,
        round_index: int,
    ) -> list[SourceCandidate]:
        results = await provider.search(query, limit, round_index=round_index)
        if isinstance(provider, AlphaXivProviderClient):
            enriched: list[SourceCandidate] = []
            for candidate in results[:limit]:
                enriched.append(candidate)
                if candidate.content or "full_text" not in provider.capabilities:
                    continue
                paper_ref = _paper_reference_from_url(str(candidate.url))
                if not paper_ref:
                    continue
                try:
                    payload = await provider.get_paper(paper_ref, full_text=True)
                    content = payload.get("content") or payload.get("fullText") or payload.get("report") or ""
                    if content:
                        candidate.content = content
                except Exception:
                    pass
            return enriched
        return results

    def _advance(self, job_id: str, stage: ResearchStage, progress: float, message: str) -> None:
        self._repository.update_job(job_id, status=ResearchJobStatus.RUNNING, stage=stage, progress=progress)
        self._repository.append_activity(job_id, stage, message)


class ResearchQueryPlanner:
    def build_plan(self, request: CreateResearchJobRequest) -> ResearchPlan:
        planned_rounds = {
            "basic": 1,
            "academic": 2,
            "deep": min(3, request.max_iterations),
        }[request.depth]
        queries = self._initial_queries(request)[: max(planned_rounds, request.max_iterations)]
        objective = (
            f"Research {request.topic} for a {request.template.value} paper and produce a source-grounded draft."
        )
        return ResearchPlan(
            topic=request.topic,
            objective=objective,
            depth=request.depth,
            template=request.template,
            queries=[ResearchQuery(query=query, rationale="diversified retrieval angle") for query in queries],
            acceptance_criteria=[
                "At least two independent sources for key claims when available.",
                "Prioritize academic evidence and supplement with web sources for recent context.",
                "Reject unsupported claims before section generation.",
            ],
            planned_rounds=planned_rounds,
        )

    def _initial_queries(self, request: CreateResearchJobRequest) -> list[str]:
        topic = request.topic.strip()
        queries = [topic, f"{topic} survey", f"{topic} literature review"]
        if request.depth != "basic":
            queries.extend([f"{topic} empirical results", f"{topic} benchmarks"])
        if request.depth == "deep":
            queries.extend([f"{topic} open questions", f"{topic} code repository"])
        if request.description:
            queries.insert(1, f"{topic} {request.description.strip()}")
        return _dedupe_queries(queries)


def _paper_reference_from_url(url: str) -> str | None:
    match = re.search(r"/(?:abs|pdf)/([^/?#]+)", url)
    if match:
        return match.group(1).removesuffix(".pdf")
    return None


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        normalized = " ".join(query.split()).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(query)
    return deduped


def _failure_category(exc: Exception) -> str:
    if isinstance(exc, ProviderError):
        return exc.category
    if isinstance(exc, RuntimeError):
        return "research_failed"
    return "internal_error"


def _safe_failure_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__
