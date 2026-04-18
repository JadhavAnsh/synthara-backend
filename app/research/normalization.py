import re

from app.schemas.research import RejectedSource, SourceCandidate, SourceRecord
from app.utils.ids import stable_id


def normalize_sources(candidates: list[SourceCandidate], max_sources: int) -> tuple[list[SourceRecord], list[RejectedSource]]:
    records: list[SourceRecord] = []
    rejected: list[RejectedSource] = []
    seen: set[str] = set()
    for candidate in candidates:
        dedupe_key = _dedupe_key(candidate)
        record = SourceRecord(
            source_id=stable_id("src", dedupe_key),
            provider=candidate.provider,
            source_type=candidate.source_type,
            title=candidate.title,
            url=candidate.url,
            authors=candidate.authors,
            year=candidate.year,
            abstract=candidate.abstract,
            content=candidate.content,
            discovery_query=candidate.discovery_query,
            discovery_round=candidate.discovery_round,
            score=candidate.score,
            metadata=candidate.metadata,
        )
        if dedupe_key in seen:
            rejected.append(RejectedSource(source=record, reason="duplicate"))
            continue
        if len(records) >= max_sources:
            rejected.append(RejectedSource(source=record, reason="source_limit"))
            continue
        seen.add(dedupe_key)
        records.append(record)
    return records, rejected


def _dedupe_key(candidate: SourceCandidate) -> str:
    external_ids = candidate.metadata.get("external_ids") or {}
    doi = external_ids.get("DOI") or external_ids.get("doi")
    if doi:
        return f"doi:{str(doi).lower()}"
    arxiv_id = external_ids.get("ArXiv") or external_ids.get("arXiv") or _arxiv_id_from_url(str(candidate.url))
    if arxiv_id:
        return f"arxiv:{str(arxiv_id).lower()}"
    url = str(candidate.url).rstrip("/").lower()
    if url:
        return url
    return re.sub(r"\W+", " ", candidate.title).strip().lower()


def _arxiv_id_from_url(url: str) -> str | None:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url, flags=re.IGNORECASE)
    if match:
        return match.group(1).removesuffix(".pdf")
    return None
