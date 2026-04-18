from pydantic import BaseModel, Field

from app.schemas.research import CitationStyle, PaperTemplateType


class TemplateConfig(BaseModel):
    template: PaperTemplateType
    label: str
    citation_style: CitationStyle
    sections: list[str] = Field(default_factory=list)
    formatting_rules: dict[str, str | int] = Field(default_factory=dict)


_TEMPLATES = {
    PaperTemplateType.IEEE: TemplateConfig(
        template=PaperTemplateType.IEEE,
        label="IEEE Conference Paper",
        citation_style=CitationStyle.NUMERIC,
        sections=[
            "Abstract",
            "Introduction",
            "Literature Review",
            "Methodology",
            "Results",
            "Discussion",
            "Conclusion",
        ],
        formatting_rules={"font_family": "Times New Roman", "font_size": 10, "line_spacing": "single"},
    ),
    PaperTemplateType.HARVARD: TemplateConfig(
        template=PaperTemplateType.HARVARD,
        label="Harvard Research Paper",
        citation_style=CitationStyle.AUTHOR_YEAR,
        sections=[
            "Abstract",
            "Introduction",
            "Literature Review",
            "Methodology",
            "Results",
            "Discussion",
            "Conclusion",
        ],
        formatting_rules={"font_family": "Times New Roman", "font_size": 12, "line_spacing": "1.5"},
    ),
}


def get_template_config(template: PaperTemplateType) -> TemplateConfig:
    return _TEMPLATES[template]
