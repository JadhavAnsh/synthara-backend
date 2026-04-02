from fastapi import APIRouter

router = APIRouter(tags=["root"])


@router.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Synthara Research Backend",
        "status": "ok",
        "docs_hint": "Use /health for a minimal health check.",
    }
