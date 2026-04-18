# Backend Implementation Plan

Purpose: translate the updated root [PRD.md](/E:/Synthara/PRD.md) into a concrete implementation roadmap for the Python backend under `backend/`.

This plan assumes the product boundary is:

- Next.js APIs handle auth, credits, and user-facing session composition.
- FastAPI handles research, knowledge retrieval, paper generation, citations, and export preparation.

It also assumes the backend should use the local `feynman/` repository as a design reference for autonomous research behavior, but the implementation itself must be rewritten in Python and shaped around API contracts rather than CLI workflows.

## Current Backend State

- FastAPI scaffold exists in [main.py](/E:/Synthara/backend/app/main.py).
- Root and health routes exist in [root.py](/E:/Synthara/backend/app/api/routes/root.py) and [health.py](/E:/Synthara/backend/app/api/routes/health.py).
- Only a partial research schema exists in [research.py](/E:/Synthara/backend/app/schemas/research.py).
- Package folders for `agents`, `orchestration`, `repositories`, `services`, and `formatters` exist, but they are placeholders.
- No research pipeline, no knowledge base layer, no paper generator, no citation engine, and no export pipeline have been implemented yet.

## Backend Principles

- Rebuild Feynman-like research behavior as Python services, not as embedded CLI workflows.
- Keep HTTP handlers thin.
- Persist structured artifacts, not just freeform summaries.
- Treat citations and provenance as first-class data.
- Generate papers section by section.
- Keep the backend stateless at the API layer and stateful in repositories/job storage.

## Target Backend Shape

The current `app/` layout should evolve toward:

```text
backend/app/
  api/
    routes/
  research/
  knowledge/
  paper/
  citations/
  templates/
  export/
  repositories/
  schemas/
  services/
  utils/
```

Recommended ownership:

- `api/`: route contracts and response envelopes
- `research/`: Feynman-inspired research orchestration and source ingestion
- `knowledge/`: chunking, embeddings, retrieval, and evidence storage
- `paper/`: section planning, section generation, and document assembly
- `citations/`: source normalization and style-specific citation rendering
- `templates/`: IEEE and Harvard template definitions
- `export/`: Markdown first, then DOCX and PDF
- `repositories/`: persistence interfaces and implementations
- `services/`: application-level orchestration used by routes

## Reference From Feynman

We should study `feynman/` for workflow behavior, especially:

- iterative search and refinement
- source-heavy note generation
- role separation between research, writing, review, and verification
- durable working memory

We should not copy:

- file artifact conventions as the product surface
- CLI-first assumptions
- markdown-only outputs
- product-level auth/account logic

The Python rewrite should convert those ideas into:

- typed schemas
- job-oriented orchestration
- repository-backed state
- section-aware retrieval and drafting

## Phase 1 Scope

Phase 1 is the real MVP backend, not a generic research service.

It should support:

- creating a research job for a paper topic
- running autonomous source discovery and extraction
- building a structured knowledge object
- generating `Abstract` and `Introduction`
- attaching basic citations
- returning an editable paper document payload
- exporting Markdown

It does not need in phase 1:

- production billing logic
- multi-user collaboration
- DOCX/PDF parity
- Redis queue infrastructure
- full multi-agent parallelism

## Feature Breakdown

## Feature: Backend Foundation And Shared Contracts

**Description**
Prepare the FastAPI backend for a split architecture where the Python app owns research workflows and the Next.js app calls it as a product service.

**Tasks**

- Add configuration for backend-only concerns such as model provider settings, vector store configuration, source cache settings, and export options.
- Define shared enums/constants for job status, source providers, citation styles, paper templates, generation depth, and export types.
- Add reusable API success and error envelopes.
- Establish route registration and dependency wiring without placing business logic in handlers.

**Sub-tasks**

- Create a settings module using `pydantic-settings`.
- Add shared helpers for IDs, timestamps, and correlation IDs.
- Define standard backend exception types for validation, provider, retrieval, citation, export, and persistence errors.
- Keep auth and credit validation out of the Python backend surface except for trusted service-to-service metadata passed from Next.js.

**Test Cases**

- App boots with the expanded module layout.
- Shared response envelopes serialize correctly.
- Settings load correctly from environment variables.

## Feature: Research Job And Document Schemas

**Description**
Replace the current minimal research schema with the actual contracts required for a topic-to-paper workflow.

**Tasks**

- Define request models for creating a paper-generation job.
- Define response models for research job status, structured knowledge, paper document payloads, citations, and export jobs.
- Define section-level models so the frontend can edit and regenerate individual sections.

**Sub-tasks**

- Add `PaperTemplateType` enum: `IEEE`, `Harvard`.
- Add `GenerationDepth` enum: `basic`, `academic`, `deep`.
- Define `SourceRecord`, `EvidenceChunk`, `KnowledgeBaseEntry`, `CitationReference`, `PaperSection`, `PaperDocument`, and `ResearchJob`.
- Include provenance fields that connect paragraphs or sections to source IDs.

**Test Cases**

- Valid topic submissions produce schema-valid jobs.
- Invalid template/depth values fail validation.
- Paper document payloads preserve section ordering and citation metadata.

## Feature: Repository Layer And Persistence Abstractions

**Description**
Introduce repositories for jobs, structured knowledge, source records, paper documents, and logs.

**Tasks**

- Define repository interfaces for jobs, sources, evidence chunks, paper documents, and activity logs.
- Implement in-memory repositories first so orchestration can be built without blocking on production persistence.
- Define lifecycle transitions for draft generation and section regeneration.

**Sub-tasks**

- Persist the original topic request and generation parameters.
- Persist structured research output rather than raw text only.
- Persist the editable paper document separately from raw research artifacts.
- Store logs for research, retrieval, generation, citation, and export stages.

**Test Cases**

- A created job is retrievable with request metadata intact.
- Knowledge records and paper documents can be stored and reloaded by job ID.
- Invalid state transitions are rejected.

## Feature: Feynman-Inspired Research Engine In Python

**Description**
Build the core research engine in Python by adapting Feynman's workflow concepts into services that can run behind FastAPI.

**Tasks**

- Create a research orchestrator that performs iterative search, source selection, summarization, and refinement.
- Create provider abstractions for arXiv, Semantic Scholar, and web search/scraping.
- Normalize all source results into a common source schema.

**Sub-tasks**

- Implement a loop like `search -> summarize -> refine -> store`.
- Keep intermediate state in structured memory objects rather than markdown files.
- Tag findings with source IDs, URLs, authors, year, and retrieval metadata.
- Preserve extension points for later multi-agent roles such as reviewer and verifier.

**Test Cases**

- Research runs produce structured source and claim outputs.
- The loop can stop when evidence quality reaches a threshold or max iterations.
- Source normalization keeps provider-specific metadata without breaking the common contract.

## Feature: Structured Knowledge Layer

**Description**
Convert raw research output into retrieval-ready knowledge for downstream section generation.

**Tasks**

- Implement chunking for source content and extracted findings.
- Define the structured knowledge object returned by research.
- Prepare interfaces for embeddings and vector retrieval.

**Sub-tasks**

- Store `topics`, `key_points`, `citations`, and `raw_sources`.
- Add evidence chunk records linked to source IDs.
- Add a retrieval service that can fetch the top relevant chunks for a target section.
- Start with a simple in-memory retriever or deterministic stub if embeddings are not ready yet.

**Test Cases**

- Raw sources are converted into knowledge objects with evidence chunks.
- Retrieval returns section-relevant evidence in deterministic tests.
- Every key point references at least one real source ID.

## Feature: Template System

**Description**
Model paper formats explicitly so generation and export do not rely on ad hoc prompt text.

**Tasks**

- Define template configs for IEEE and Harvard.
- Represent required sections, citation style, and export/rendering metadata in code.
- Expose template lookup to the paper generator and citation engine.

**Sub-tasks**

- Add a `templates/registry.py`.
- Define section order and required sections per template.
- Store formatting metadata such as font family, size, and citation style.

**Test Cases**

- Template registry returns the correct template by key.
- IEEE and Harvard configs produce different citation style metadata.
- Required sections are enforced for document assembly.

## Feature: Section-Based Paper Generator

**Description**
Generate editable paper documents section by section using retrieved evidence and template constraints.

**Tasks**

- Build a section planner for paper structure.
- Build a section generator that takes evidence chunks, template config, and style options.
- Assemble generated sections into a single paper document payload.

**Sub-tasks**

- Phase 1 must support `Abstract` and `Introduction`.
- Design the API to support future sections without changing the document contract.
- Keep document context available so later sections can remain coherent with earlier accepted sections.
- Store per-section provenance and citation references.

**Test Cases**

- `Abstract` and `Introduction` can be generated from a valid knowledge object.
- Sections contain citation references tied to real source IDs.
- Document assembly preserves template-defined section order.

## Feature: Citation Engine

**Description**
Build a citation engine that can transform internal source references into display-ready IEEE or Harvard citations.

**Tasks**

- Normalize source metadata into a citation-ready schema.
- Implement style renderers for numeric and author-year references.
- Support late-stage reference ordering so citations remain consistent after regeneration.

**Sub-tasks**

- Use stable internal source IDs before final rendering.
- Render IEEE citations as numbered references.
- Render Harvard citations as author-year references.
- Produce a references list from the actual cited sources in the paper document.

**Test Cases**

- Citation rendering changes correctly between IEEE and Harvard.
- Reordering or regenerating a section updates numeric references correctly.
- References list contains only cited sources.

## Feature: Section Regeneration API

**Description**
Design the backend around editable documents, which means regenerating only one section must be a first-class flow.

**Tasks**

- Add an endpoint/service for section regeneration.
- Retrieve only the evidence relevant to the selected section.
- Re-run citation assignment for the modified section and document references.

**Sub-tasks**

- Accept the current document context plus section ID.
- Preserve unaffected sections.
- Recompute references deterministically after section replacement.

**Test Cases**

- Regenerating `Introduction` updates only that section.
- Citation ordering remains valid after replacement.
- Requests for unknown section IDs fail cleanly.

## Feature: Export Pipeline

**Description**
Support export from the structured paper document model rather than from arbitrary markdown text.

**Tasks**

- Implement Markdown export in phase 1.
- Define export adapter interfaces for DOCX and PDF.
- Preserve template metadata in export requests.

**Sub-tasks**

- Convert structured sections into Markdown.
- Include references at the bottom of the document.
- Design PDF export around a future LaTeX renderer, especially for IEEE.

**Test Cases**

- Markdown export produces the expected section order and references.
- Export fails cleanly if the document is incomplete or missing.
- Export output remains stable for the same document input.

## Feature: Backend API Surface

**Description**
Expose a stable API for the Next.js application to create jobs, inspect status, fetch documents, regenerate sections, and export outputs.

**Tasks**

- Add `POST /api/research/jobs`
- Add `GET /api/research/jobs/{job_id}`
- Add `GET /api/research/jobs/{job_id}/document`
- Add `POST /api/research/jobs/{job_id}/sections/{section_id}/regenerate`
- Add `POST /api/research/jobs/{job_id}/exports/markdown`

**Sub-tasks**

- Standardize response envelopes.
- Return job progress and failure details cleanly.
- Accept trusted metadata from Next.js such as `user_id` and `credit_context` if needed, but do not implement billing logic here.

**Test Cases**

- Job creation returns a new job record.
- Document retrieval returns the generated editable payload.
- Regeneration endpoint updates a single section.
- Markdown export returns a downloadable payload or persisted artifact reference.

## Feature: Observability And Testing Baseline

**Description**
Add enough automated coverage and logging to evolve the backend safely as the research engine grows in complexity.

**Tasks**

- Add unit tests for repositories, template registry, citation rendering, retrieval, and section generation.
- Add API tests for the main research/document/export routes.
- Define structured logs for each major stage.

**Sub-tasks**

- Log `job_id`, `correlation_id`, `stage`, `status`, and timing fields.
- Add deterministic fixtures for source records and knowledge objects.
- Ensure failures are categorized clearly.

**Test Cases**

- Research job happy path completes with deterministic stubs.
- Section regeneration happy path completes with deterministic stubs.
- Citation rendering tests cover IEEE and Harvard.
- Export tests cover Markdown assembly.

## Suggested Delivery Order

1. Expand schemas and shared response contracts.
2. Add repository interfaces and in-memory implementations.
3. Build template registry and citation primitives.
4. Build the Python research engine skeleton inspired by Feynman.
5. Add structured knowledge extraction and retrieval.
6. Implement section generation for `Abstract` and `Introduction`.
7. Add document retrieval and section regeneration routes.
8. Add Markdown export.
9. Add tests and logging hardening.

## Deferred Work

- Replace in-memory repositories with durable storage.
- Add real embedding storage and vector DB integration.
- Add dedicated verifier and critic passes as separate services or agents.
- Add DOCX and PDF export adapters.
- Add Redis or another async job system for long-running research work.
- Add richer provenance UI support once the frontend editor is wired.

## Immediate Build Guidance

When implementing from this plan:

- do not port Feynman's TypeScript runtime directly into the backend
- do study its research loop, role separation, and source-grounding patterns
- do return structured document objects for the Next.js editor
- do keep auth and credit logic in Next.js APIs
- do treat citations, provenance, and section regeneration as core backend concerns from day one
