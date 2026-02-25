from pydantic import BaseModel, Field


class LegalQuestionRequest(BaseModel):
    question: str = Field(..., min_length=5)
    court_level: str = Field(default="trial")
    state: str = Field(default="unknown")
    stage: str = Field(default="investigation")
    district: str = Field(default="")
    response_language: str = Field(default="english")
    template_type: str = Field(default="auto")


class LegalQuestionResponse(BaseModel):
    disclaimer: str
    interpreted_issue: str
    urgency_level: str
    citizen_brief: dict
    mapped_sections: list[dict]
    likely_precedents: list[dict]
    citation_hits: list[dict]
    risk_signals: list[str]
    local_process_map: list[str]
    district_playbook: list[str]
    filing_templates: list[dict]
    action_window_24h: list[str]
    strategy_steps: list[str]
    document_checklist: list[str]
    confidence: str
    llm_fallback: dict | None = None


class FIRAnalysisResponse(BaseModel):
    disclaimer: str
    extracted_sections: list[dict]
    red_flags: list[str]
    procedural_gaps: list[str]
    suggested_next_steps: list[str]
    precedent_hints: list[dict]


class CaseCreateRequest(BaseModel):
    case_title: str = Field(..., min_length=3)
    client_name: str = Field(..., min_length=2)
    case_type: str = Field(default="criminal")
    court_level: str = Field(default="trial")
    state: str = Field(default="unknown")
    facts_summary: str = Field(..., min_length=10)


class CaseResponse(BaseModel):
    id: int
    case_title: str
    client_name: str
    case_type: str
    court_level: str
    state: str
    facts_summary: str
    created_at: str


class CaseUpdateRequest(BaseModel):
    case_title: str = Field(..., min_length=3)
    client_name: str = Field(..., min_length=2)
    case_type: str = Field(default="criminal")
    court_level: str = Field(default="trial")
    state: str = Field(default="unknown")
    facts_summary: str = Field(..., min_length=10)


class DeleteResponse(BaseModel):
    status: str
    message: str


class PrecedentSearchRequest(BaseModel):
    query: str = Field(..., min_length=5)
    state: str = Field(default="telangana")
    limit: int = Field(default=5, ge=1, le=20)


class PrecedentSearchResponse(BaseModel):
    query: str
    results: list[dict]


class IngestResponse(BaseModel):
    status: str
    message: str
    inserted: int


class CorpusStatusResponse(BaseModel):
    supported_states: list[str]
    statutes: list[dict]
    precedents: list[dict]


class PublicIngestRequest(BaseModel):
    state: str = Field(default="telangana")
    document_type: str = Field(default="precedent")
    urls: list[str] = Field(default_factory=list)


class PublicIngestResponse(BaseModel):
    status: str
    message: str
    attempted: int
    inserted: int
    failed_urls: list[str]


class InstantSolveRequest(BaseModel):
    question: str = Field(..., min_length=5)
    state: str = Field(default="telangana")
    response_language: str = Field(default="english")


class InstantSolveResponse(BaseModel):
    disclaimer: str
    interpreted_issue: str
    inferred_stage: str
    inferred_court_level: str
    inferred_district: str
    inferred_template_type: str
    urgency_level: str
    one_shot_summary: str
    top_actions: list[str]
    draft_preview: str
    confidence: str
    full_result: LegalQuestionResponse
