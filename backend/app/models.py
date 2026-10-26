from typing import Any, Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ClaimTypeId = Literal["inpatient", "outpatient", "critical_illness"]
Answer = Literal["unknown", "yes", "no"]
DocumentStatus = Literal["not_started", "uploaded", "processing", "precheck_passed", "needs_attention", "manual_ready", "not_applicable"]


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


class VisitDates(StrictModel):
    admission: str | None = Field(default=None, max_length=40)
    discharge: str | None = Field(default=None, max_length=40)
    visit: str | None = Field(default=None, max_length=40)
    discharge_pending: bool = False

    @field_validator("admission", "discharge", "visit")
    @classmethod
    def partial_date_only(cls, value):
        from .ai.dialogue_privacy import redact_text
        if value is not None and redact_text(value) != value:
            raise ValueError("Identifying information is not a date")
        if value is not None and not re.fullmatch(r"[0-9一二三四五六七八九十百零〇民國年月日號週周星期上下本這昨今前後初底末季到至間\s/.,~～()（）-]{1,40}", value):
            raise ValueError("Dates retain only the supplied partial date")
        return value


class PolicyProduct(StrictModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    version: str | None = Field(default=None, max_length=80)
    verification_status: Literal["unverified"] = "unverified"

    @field_validator("code")
    @classmethod
    def no_identifiers_in_code(cls, value):
        from .ai.dialogue_privacy import redact_text
        if redact_text(value) != value:
            raise ValueError("Identifying information is not a product code")
        return value

    @field_validator("version")
    @classmethod
    def version_label_only(cls, value):
        from .ai.dialogue_privacy import redact_text
        if value is not None and redact_text(value) != value:
            raise ValueError("Identifying information is not a product version")
        if value is not None and not re.fullmatch(r"[A-Za-z0-9._/年月日版第次修訂逕保單商品條款附約\s()（）-]{1,80}", value):
            raise ValueError("Product version must be a version label")
        return value


class CaseDetails(StrictModel):
    insured_relation: Literal["unknown", "self", "spouse", "parent", "child", "other"] = "unknown"
    diagnosis_name: str | None = Field(default=None, max_length=120)
    surgery_name: str | None = Field(default=None, max_length=120)
    surgery_date: str | None = Field(default=None, max_length=40)
    visit_dates: VisitDates = Field(default_factory=VisitDates)
    policy_products: list[PolicyProduct] = Field(default_factory=list, max_length=10)
    deferred_fields: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("diagnosis_name", "surgery_name", "surgery_date")
    @classmethod
    def no_obvious_identifiers(cls, value):
        from .ai.dialogue_privacy import redact_text
        if value is not None and redact_text(value) != value:
            raise ValueError("Identifying information is not a case detail")
        return value

    @field_validator("surgery_date")
    @classmethod
    def surgery_partial_date_only(cls, value):
        return VisitDates.partial_date_only(value)

    @field_validator("deferred_fields")
    @classmethod
    def deferred_field_names_only(cls, values):
        allowed = {"cause", "surgery", "receipt_type", "payment_method", "inpatient", "outpatient", "emergency", "critical_diagnosis",
                   "insured_relation", "diagnosis_name", "surgery_name", "surgery_date", "visit_dates.admission", "visit_dates.discharge", "visit_dates.visit", "policy_products"}
        if any(value not in allowed for value in values):
            raise ValueError("Only known field identifiers may be deferred")
        return list(dict.fromkeys(values))


class PendingQuestion(StrictModel):
    field: str = Field(min_length=1, max_length=80)
    kind: Literal["fact", "proposal"]
    asked_at_revision: int = Field(default=0, ge=0)
    prompt: str = Field(default="", max_length=500)
    options: list[dict[str, str]] = Field(default_factory=list, max_length=10)


class Proposal(StrictModel):
    id: str
    base_revision: int = Field(ge=0)
    changes: list[dict[str, Any]]


class DialogueState(StrictModel):
    facts: dict[str, str] = Field(default_factory=dict)
    conditions: dict[str, str] = Field(default_factory=dict)
    details: CaseDetails = Field(default_factory=CaseDetails)
    deferred_fields: list[str] = Field(default_factory=list)
    pending_question: PendingQuestion | None = None
    active_proposal: dict[str, Any] | None = None


class CreateCase(StrictModel):
    entry_path: Literal["guided", "direct"]
    claim_type_id: ClaimTypeId | None = None
    conditions: Conditions = Field(default_factory=Conditions)
    details: CaseDetails = Field(default_factory=CaseDetails)


class UpdateCase(StrictModel):
    claim_type_id: ClaimTypeId | None = None
    conditions: Conditions | None = None
    details: CaseDetails | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    proposal_id: str | None = Field(default=None, min_length=1, max_length=100)
    proposal_action: Literal["accept", "reject"] | None = None

    @model_validator(mode="after")
    def no_null_conditions(self):
        if "conditions" in self.model_fields_set and self.conditions is None:
            raise ValueError("conditions cannot be null")
        if "details" in self.model_fields_set and self.details is None:
            raise ValueError("details cannot be null")
        if self.proposal_action and (not self.proposal_id or self.expected_revision is None):
            raise ValueError("Proposal actions require id and revision")
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
    analysis_id: str | None = Field(default=None, min_length=1, max_length=100)


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
    response_type: Literal["clarification", "claim_suggestion", "case_update_proposal", "answer", "uncertain"]
    message: str = Field(min_length=1, max_length=16000)
    suggested_claim_types: list[ClaimType]
    missing_information: list[str]
    source_references: list[Source]
    proposed_case_updates: UpdateCase
    requires_human_review: bool
    provider: str
    is_simulated: bool
    pending_question: PendingQuestion | None = None
    dialogue_state: DialogueState | None = None
    proposal: Proposal | None = None


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
    bounding_box: BoundingBox | None = None
    location_status: Literal["label", "unlocated", "page"] = "unlocated"
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
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


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
    details: CaseDetails = Field(default_factory=CaseDetails)
    dialogue_state: DialogueState = Field(default_factory=DialogueState)
    revision: int = Field(default=0, ge=0)
    documents: list[Document]
    messages: list[Message]
    created_at: str
    updated_at: str
