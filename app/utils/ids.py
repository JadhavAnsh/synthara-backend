from hashlib import sha256
from uuid import uuid4


def new_job_id() -> str:
    return f"job_{uuid4().hex}"


def stable_id(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
