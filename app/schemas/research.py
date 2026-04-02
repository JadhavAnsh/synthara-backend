from typing import Literal

from pydantic import BaseModel, Field


ResearchMode = Literal["decision", "paper"]


class ResearchRequest(BaseModel):
    goal: str = Field(min_length=1)
    description: str = Field(default="")
    paper_format: Literal["IEEE", "APA"] | None = None
