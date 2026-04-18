# Backend

Synthara's Python backend owns:

- async research jobs
- source discovery across alphaXiv, arXiv, and Tavily
- structured knowledge + provenance
- initial paper document generation
- section regeneration
- Markdown export

## Local setup

1. `uv sync`
2. copy `.env.example` to `.env`
3. start the alphaXiv bridge from [`backend/alphaxiv-bridge`](E:/Synthara/backend/alphaxiv-bridge/README.md)
4. run `uv run uvicorn app.main:app --reload`

The backend exposes:

- `POST /api/research/jobs`
- `GET /api/research/jobs/{job_id}`
- `GET /api/research/jobs/{job_id}/knowledge`
- `GET /api/research/jobs/{job_id}/document`
- `POST /api/research/jobs/{job_id}/sections/{section_id}/regenerate`
- `POST /api/research/jobs/{job_id}/exports/markdown`
