from typing import Literal

from pydantic import BaseModel, Field


Category = Literal["attendance", "exams", "fees", "hostel", "out_of_scope"]
Status = Literal["supported", "unsupported", "conflict", "clarification_needed", "refused"]
Confidence = Literal["High", "Medium", "Low"]


class Citation(BaseModel):
    source_document: str
    source_section: str
    source_quote: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    prompt_version: Literal["v1", "v2", "v3"] = "v3"


class AnswerResponse(BaseModel):
    category: Category
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence
    status: Status
    contact: str | None = None
    mode: Literal["demo", "gemini"]
    prompt_version: str


class PolicySection(BaseModel):
    document: str
    section: str
    title: str
    text: str
    fictional: bool


class PolicyDocument(BaseModel):
    title: str
    filename: str
    fictional: bool
    sections: list[PolicySection]
