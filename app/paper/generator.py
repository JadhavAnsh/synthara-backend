from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.citations.engine import render_inline_citation
from app.schemas.research import (
    PaperDocument,
    PaperSection,
    ParagraphProvenance,
    StructuredKnowledge,
)
from app.templates.registry import get_template_config


@dataclass
class GeminiClient:
    http_client: httpx.AsyncClient
    api_key: str | None
    model: str
    endpoint_template: str
    temperature: float

    async def complete(self, prompt: str) -> str | None:
        if not self.api_key or self.http_client is None:
            return None
        try:
            endpoint = self.endpoint_template.format(model=self.model)
            response = await self.http_client.post(
                endpoint,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": self.temperature},
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError:
            return None
        candidates = payload.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(texts).strip() or None


class PaperDocumentGenerator:
    def __init__(self, gemini_client: GeminiClient) -> None:
        self._gemini_client = gemini_client

    async def generate_document(self, knowledge: StructuredKnowledge) -> PaperDocument:
        title = knowledge.plan.topic.strip().title()
        references = knowledge.citations
        sections = [
            await self._build_section("abstract", "Abstract", 0, knowledge, references),
            await self._build_section("introduction", "Introduction", 1, knowledge, references),
        ]
        cited_ids = {source_id for section in sections for source_id in section.citation_source_ids}
        filtered_references = [reference for reference in references if reference.source_id in cited_ids]
        return PaperDocument(
            job_id=knowledge.job_id,
            title=title,
            template=knowledge.plan.template,
            depth=knowledge.plan.depth,
            sections=sections,
            references=filtered_references,
        )

    async def regenerate_section(
        self,
        document: PaperDocument,
        knowledge: StructuredKnowledge,
        section_id: str,
        instructions: str,
    ) -> PaperDocument:
        sections: list[PaperSection] = []
        for section in document.sections:
            if section.section_id == section_id:
                replacement = await self._build_section(
                    section.section_id,
                    section.heading,
                    section.order,
                    knowledge,
                    document.references,
                    instructions=instructions,
                    prior_sections=[item for item in document.sections if item.order < section.order],
                )
                sections.append(replacement)
            else:
                sections.append(section)
        cited_ids = {source_id for section in sections for source_id in section.citation_source_ids}
        filtered_references = [reference for reference in knowledge.citations if reference.source_id in cited_ids]
        return PaperDocument(
            job_id=document.job_id,
            title=document.title,
            template=document.template,
            depth=document.depth,
            sections=sections,
            references=filtered_references,
        )

    async def _build_section(
        self,
        section_id: str,
        heading: str,
        order: int,
        knowledge: StructuredKnowledge,
        references,
        *,
        instructions: str = "",
        prior_sections: list[PaperSection] | None = None,
    ) -> PaperSection:
        claims = knowledge.claims[:4] if section_id == "abstract" else knowledge.claims[:6]
        source_ids = []
        provenance: list[ParagraphProvenance] = []
        paragraphs: list[str] = []
        for claim in claims:
            if claim.support_status == "rejected":
                continue
            source_id = claim.source_ids[0]
            source_ids.append(source_id)
            citation = render_inline_citation(source_id, references, get_template_config(knowledge.plan.template).citation_style)
            paragraph = f"{claim.claim} {citation}".strip()
            provenance.append(
                ParagraphProvenance(
                    paragraph_id=f"{section_id}-{len(provenance)+1}",
                    text=paragraph,
                    source_ids=claim.source_ids,
                    chunk_ids=claim.chunk_ids,
                )
            )
            paragraphs.append(paragraph)

        base_text = "\n\n".join(paragraphs) if paragraphs else "Insufficient evidence to draft this section."
        prompt = (
            f"Write the {heading} section for a research paper about {knowledge.plan.topic}.\n"
            f"Use only the evidence below.\n\n{base_text}\n\n"
            f"Additional instructions: {instructions or 'None'}\n"
        )
        if prior_sections:
            prompt += "\nAccepted prior sections:\n" + "\n\n".join(section.content for section in prior_sections)
        generated = await self._gemini_client.complete(prompt)
        content = generated or base_text
        if not provenance:
            provenance.append(
                ParagraphProvenance(
                    paragraph_id=f"{section_id}-1",
                    text=content,
                    source_ids=[],
                    chunk_ids=[],
                )
            )
        return PaperSection(
            section_id=section_id,
            heading=heading,
            order=order,
            content=content,
            citation_source_ids=list(dict.fromkeys(source_ids)),
            provenance=provenance,
        )
