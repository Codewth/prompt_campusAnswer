from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


Category = Literal["attendance", "exams", "fees", "hostel", "scholarships", "campus", "out_of_scope"]
Status = Literal["supported", "unsupported", "conflict", "clarification_needed", "refused"]
Confidence = Literal["High", "Medium", "Low"]
ResponseType = Literal[
    "general_conversation",
    "general_knowledge",
    "verified_policy",
    "policy_unavailable",
    "demo_policy",
    "mixed",
]
ResponseLabel = Literal[
    "General conversation",
    "General AI knowledge",
    "Verified university policy",
    "Policy information unavailable",
    "Fictional policy demonstration",
    "Mixed response",
]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    response_type: ResponseType | None = None
    category: Category | None = None


class Citation(BaseModel):
    source_document: str
    source_section: str
    source_quote: str
    collection: Literal["official", "demo"] = "demo"
    academic_year: str | None = None
    source_url: str | None = None
    page: int | None = None
    extraction_method: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    prompt_version: Literal["v1", "v2", "v3"] = "v3"
    collection: Literal["official", "demo"] = "official"
    history: list[ConversationMessage] = Field(default_factory=list, max_length=12)


class StudentProfileResponse(BaseModel):
    uid: str
    name: str | None = None
    email: str | None = None
    photo_url: str | None = None
    university: str = ""
    enrollment_number: str = ""
    course: str = ""
    specialization: str = ""
    academic_year: str = ""
    semester: str = ""
    batch: str = ""
    theme: Literal["light", "dark"] = "light"
    updated_at: str | None = None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    university: str = Field(max_length=180)
    enrollment_number: str = Field(max_length=80)
    course: str = Field(max_length=150)
    specialization: str = Field(max_length=180)
    academic_year: str = Field(max_length=40)
    semester: str = Field(max_length=40)
    batch: str = Field(max_length=40)

    @field_validator(
        "name",
        "university",
        "enrollment_number",
        "course",
        "specialization",
        "academic_year",
        "semester",
        "batch",
    )
    @classmethod
    def trim_profile_fields(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        if info.field_name == "name" and not value:
            raise ValueError("Name cannot be empty.")
        return value


class ProfileSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal["light", "dark"]


class AnswerSegment(BaseModel):
    response_type: ResponseType
    response_label: ResponseLabel
    category: Category
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence | None = None
    status: Status
    contact: str | None = None
    mode: Literal["demo", "gemini", "predefined"]


class AnswerResponse(BaseModel):
    category: Category
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence | None = None
    status: Status
    contact: str | None = None
    mode: Literal["demo", "gemini", "predefined"]
    prompt_version: str
    collection: Literal["official", "demo"] = "demo"
    response_type: ResponseType = "verified_policy"
    response_label: ResponseLabel = "Verified university policy"
    segments: list[AnswerSegment] = Field(default_factory=list)


class PolicySection(BaseModel):
    document: str
    section: str
    title: str
    text: str
    fictional: bool
    collection: Literal["official", "demo"] = "demo"
    source_type: Literal["official", "fictional", "uploaded"] = "fictional"
    document_id: str | None = None
    academic_year: str | None = None
    source_url: str | None = None
    source_page: str | None = None
    page: int | None = None
    extraction_method: str | None = None


class PolicyDocument(BaseModel):
    title: str
    filename: str
    fictional: bool
    sections: list[PolicySection]
    collection: Literal["official", "demo"] = "demo"
    source_type: Literal["official", "fictional", "uploaded"] = "uploaded"
    academic_year: str | None = None
    source_url: str | None = None
    source_page: str | None = None
    category: str | None = None
    pages: int | None = None
    indexed_chunks: int = 0
    extraction_status: str | None = None
