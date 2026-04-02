from fastapi import FastAPI

from app.api.routes import health_router, root_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Synthara Research Backend",
        version="0.1.0",
        description="Backend scaffold for the Synthara autonomous research system.",
    )
    app.include_router(root_router)
    app.include_router(health_router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
