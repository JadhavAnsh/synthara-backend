from app.schemas.research import CitationReference, CitationStyle


def render_inline_citation(
    source_id: str,
    references: list[CitationReference],
    style: CitationStyle,
) -> str:
    index_map = {reference.source_id: index + 1 for index, reference in enumerate(references)}
    reference = next((item for item in references if item.source_id == source_id), None)
    if reference is None:
        return ""
    if style == CitationStyle.NUMERIC:
        return f"[{index_map[source_id]}]"
    author = reference.authors[0] if reference.authors else reference.title.split(" ")[0]
    year = reference.year or "n.d."
    return f"({author}, {year})"


def render_reference_list(references: list[CitationReference], style: CitationStyle) -> list[str]:
    lines: list[str] = []
    for index, reference in enumerate(references, start=1):
        author_text = ", ".join(reference.authors) if reference.authors else "Unknown Author"
        year = reference.year or "n.d."
        if style == CitationStyle.NUMERIC:
            lines.append(f"[{index}] {author_text}. {reference.title}. {year}. {reference.url}")
        else:
            lines.append(f"{author_text} ({year}) {reference.title}. Available at: {reference.url}")
    return lines
