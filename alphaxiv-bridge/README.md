# alphaXiv Bridge

Internal Node bridge that exposes alphaXiv-backed academic retrieval to the Python Synthara backend.

## Endpoints

- `GET /health`
- `GET /auth/status`
- `POST /papers/search`
- `POST /papers/get`
- `POST /papers/ask`
- `POST /repos/read`

## Notes

- This bridge is intended to run beside the Python backend inside `backend/`.
- It wraps the same `@companion-ai/alpha-hub` integration family used by Feynman.
- The Python backend should treat bridge auth/config failures as degradable provider issues and fall back to arXiv + Tavily.
