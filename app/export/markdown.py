from app.citations.engine import render_reference_list
from app.schemas.research import ExportResponse, ExportType, PaperDocument
from app.templates.registry import get_template_config


def export_markdown(document: PaperDocument) -> ExportResponse:
    template = get_template_config(document.template)
    lines = [f"# {document.title}", ""]
    for section in sorted(document.sections, key=lambda item: item.order):
        lines.append(f"## {section.heading}")
        lines.append(section.content)
        lines.append("")
    lines.append("## References")
    lines.extend(render_reference_list(document.references, template.citation_style))
    lines.append("")
    return ExportResponse(
        job_id=document.job_id,
        export_type=ExportType.MARKDOWN,
        content="\n".join(lines).strip() + "\n",
        media_type="text/markdown",
    )
