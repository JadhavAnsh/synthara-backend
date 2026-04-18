from app.repositories.research import InMemoryResearchRepository
from app.schemas.research import CreateResearchJobRequest, ResearchJobStatus, ResearchStage


def test_in_memory_repository_stores_and_updates_job() -> None:
    repository = InMemoryResearchRepository()
    job = repository.create_job("job_1", CreateResearchJobRequest(topic="citation grounding"))

    assert repository.get_job("job_1") is job
    assert job.status == ResearchJobStatus.QUEUED
    assert job.stage == ResearchStage.QUEUED

    updated = repository.update_job(
        "job_1",
        status=ResearchJobStatus.RUNNING,
        stage=ResearchStage.RESEARCHING,
        progress=0.5,
        warnings=["warning"],
    )

    assert updated.status == ResearchJobStatus.RUNNING
    assert updated.stage == ResearchStage.RESEARCHING
    assert updated.progress == 0.5
    assert updated.warnings == ["warning"]
    assert updated.updated_at >= updated.created_at


def test_append_activity_records_stage_history() -> None:
    repository = InMemoryResearchRepository()
    repository.create_job("job_1", CreateResearchJobRequest(topic="citation grounding"))

    updated = repository.append_activity("job_1", ResearchStage.PLANNING, "planning research")

    assert updated.activity[0].stage == ResearchStage.PLANNING
    assert updated.activity[0].message == "planning research"
