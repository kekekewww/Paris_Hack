from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ClaimTypeId = Literal["inpatient", "outpatient", "critical_illness"]
Answer = Literal["unknown", "yes", "no"]
DocumentStatus = Literal["not_started", "uploaded", "processing", "precheck_passed", "needs_attention", "not_applicable"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Conditions(StrictModel):
    cause: Literal["unknown", "accident", "illness"] = "unknown"
    surgery: Answer = "unknown"
    receipt_type: Literal["unknown", "actual", "daily"] = "unknown"
    payment_method: Literal["unknown", "remittance", "other"] = "unknown"
    first_claim: Answer = "unknown"
    diagnosis_has_surgery_details: Answer = "unknown"
    pathology_required_for_condition: Answer = "unknown"
    insurer_requested_medical_authorization: Answer = "unknown"
    insurer_requested_nhi_request: Answer = "unknown"


class CreateCase(StrictModel):
    entry_path: Literal["guided", "direct"]
    claim_type_id: ClaimTypeId | None = None
    conditions: Conditions = Field(default_factory=Conditions)


class UpdateCase(StrictModel):
    claim_type_id: ClaimTypeId | None = None
    conditions: Conditions | None = None

    @model_validator(mode="after")
    def no_null_conditions(self):
        if "conditions" in self.model_fields_set and self.conditions is None:
            raise ValueError("conditions cannot be null")
        return self


class MessageInput(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    document_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()


class DocumentUpdate(StrictModel):
    status: str | None = Field(default=None, max_length=30)
    confirmed_findings: list[str] | None = Field(default=None, max_length=100)


class Source(BaseModel):
    model_config = ConfigDict(extra="allow")
    source_id: str
    title: str
    official_url: str
    document_type: str
    related_claim_types: list[ClaimTypeId]
    page_number: int | None = None
    version_or_updated_at: str | None = None
    checked_at: str
    verification_status: str


class ClaimType(StrictModel):
    id: ClaimTypeId
    title: str
    description: str


class AssistantResponse(StrictModel):
    response_type: Literal["clarification", "claim_suggestion", "answer", "uncertain"]
    message: str = Field(min_length=1, max_length=16000)
    suggested_claim_types: list[ClaimType]
    missing_information: list[str]
    source_references: list[Source]
    proposed_case_updates: UpdateCase
    requires_human_review: bool
    provider: str
    is_simulated: bool


class BoundingBox(StrictModel):
    page_number: int = Field(ge=1, le=10)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class ExtractedField(StrictModel):
    field: str
    value: str
    confidence: float = Field(ge=0, le=1)
    page_number: int = Field(ge=1, le=10)


class Finding(StrictModel):
    id: str
    field: str
    field_name: str
    severity: str
    message: str
    suggestion: str
    confidence: float = Field(ge=0, le=1)
    page_number: int = Field(ge=1, le=10)
    bounding_box: BoundingBox
    source_id: str
    requires_human_review: bool


class Analysis(StrictModel):
    analysis_id: str
    document_id: str
    analysis_status: Literal["completed", "uncertain"]
    provider: str
    is_simulated: bool
    extracted_fields: list[ExtractedField]
    findings: list[Finding]
    confidence: float = Field(ge=0, le=1)
    page_number: int = Field(ge=1, le=10)
    bounding_boxes: list[BoundingBox]
    requires_human_review: bool
    disclaimer: str


class FileMetadata(StrictModel):
    name: str = Field(max_length=255)
    type: str
    size: int = Field(ge=1, le=10 * 1024 * 1024)


class Document(StrictModel):
    id: str
    title: str
    description: str
    requirement_type: Literal["required", "conditional", "optional", "unknown"]
    condition: dict[str, Any]
    applicability: bool | None
    requirement_explanation: str
    review_required: bool
    source_id: str
    official_url: str
    download_url: str | None
    example_url: str | None
    source_references: list[Source]
    status: DocumentStatus
    analysis: Analysis | None
    confirmed_findings: list[str]
    file: FileMetadata | None


class Message(StrictModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    response: AssistantResponse | None = None


class Case(StrictModel):
    id: str
    entry_path: Literal["guided", "direct"]
    claim_type_id: ClaimTypeId | None
    conditions: Conditions
    documents: list[Document]
    messages: list[Message]
    created_at: str
    updated_at: str
