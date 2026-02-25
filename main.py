from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.models import (
    CaseCreateRequest,
    CaseResponse,
    CaseUpdateRequest,
    CorpusStatusResponse,
    DeleteResponse,
    FIRAnalysisResponse,
    IngestResponse,
    InstantSolveRequest,
    InstantSolveResponse,
    LegalQuestionRequest,
    LegalQuestionResponse,
    PrecedentSearchRequest,
    PrecedentSearchResponse,
    PublicIngestRequest,
    PublicIngestResponse,
)
from app.services.case_history_service import CaseHistoryService
from app.services.citizen_guidance_service import (
    build_action_window_24h,
    build_citizen_brief,
    build_district_playbook,
    build_local_process_map,
    detect_urgency,
    extract_risk_signals,
    resolve_district,
)
from app.services.citation_corpus_service import CitationCorpusService
from app.services.fir_analyzer import FIRAnalyzer
from app.services.filing_template_service import build_filing_templates
from app.services.instant_solve_service import (
    build_one_shot_summary,
    infer_court_level,
    infer_district_from_question,
    infer_stage,
    infer_template_type,
    pick_draft_preview,
    pick_top_actions,
)
from app.services.legal_data_service import LegalDataService
from app.services.llm_fallback_service import LLMFallbackService
from app.services.precedent_service import PrecedentService
from app.services.public_ingestion_service import PublicIngestionService
from app.services.scheduler_service import DailyRefreshScheduler
from app.services.statute_service import StatuteService
from app.services.strategy_service import build_strategy, document_checklist

app = FastAPI(title="ButterflyBot")
UI_PATH = Path(__file__).resolve().parent / "app" / "ui" / "index.html"
statute_service = StatuteService()
precedent_service = PrecedentService()
fir_analyzer = FIRAnalyzer()
case_history_service = CaseHistoryService()
citation_corpus_service = CitationCorpusService()
legal_data_service = LegalDataService()
public_ingestion_service = PublicIngestionService()
llm_fallback_service = LLMFallbackService()
daily_scheduler = DailyRefreshScheduler(legal_data_service=legal_data_service, ingestion_service=public_ingestion_service)


def normalize_state(state: str) -> str:
    normalized = state.strip().lower()
    if normalized not in {"andhra pradesh", "telangana"}:
        raise HTTPException(
            status_code=400,
            detail="State must be one of: Andhra Pradesh, Telangana",
        )
    return normalized


def build_legal_response(payload: LegalQuestionRequest) -> LegalQuestionResponse:
    state = normalize_state(payload.state)
    district = resolve_district(state, payload.district)
    urgency = detect_urgency(payload.question, payload.stage)
    risk_signals = extract_risk_signals(payload.question)
    action_window_24h = build_action_window_24h(payload.stage, urgency)
    local_process_map = build_local_process_map(state, payload.stage, payload.court_level)
    district_playbook = build_district_playbook(state, district, payload.stage, payload.court_level)
    filing_templates = build_filing_templates(
        question=payload.question,
        state=state,
        district=district,
        court_level=payload.court_level,
        stage=payload.stage,
        template_type=payload.template_type,
    )
    citizen_brief = build_citizen_brief(
        payload.question,
        state,
        payload.stage,
        urgency,
        payload.response_language,
    )
    mapped_sections = statute_service.map_from_text(payload.question, state=state)
    precedents = precedent_service.search(payload.question, state=state)
    citation_hits = citation_corpus_service.search(payload.question, state=state, limit=5)
    steps = build_strategy(payload.stage, payload.court_level)
    llm_fallback = None

    if not mapped_sections and not precedents and not citation_hits:
        llm_fallback = llm_fallback_service.generate(payload.question, state)

    return LegalQuestionResponse(
        disclaimer="AI legal research assistant output. Verify with latest statutes, local rules, and certified case records.",
        interpreted_issue=payload.question.strip(),
        urgency_level=urgency,
        citizen_brief=citizen_brief,
        mapped_sections=mapped_sections,
        likely_precedents=precedents,
        citation_hits=citation_hits,
        risk_signals=risk_signals,
        local_process_map=local_process_map,
        district_playbook=district_playbook,
        filing_templates=filing_templates,
        action_window_24h=action_window_24h,
        strategy_steps=steps,
        document_checklist=document_checklist(case_type="criminal"),
        confidence="high" if mapped_sections or citation_hits else "medium",
        llm_fallback=llm_fallback,
    )


@app.on_event("startup")
def startup_init() -> None:
    case_history_service.init_schema()
    legal_data_service.init_schema()
    daily_scheduler.start()


@app.on_event("shutdown")
def shutdown_cleanup() -> None:
    daily_scheduler.shutdown()


@app.get("/")
def root() -> dict:
    return {"status": "ok", "service": "butterflybot"}


@app.get("/ui")
def ui() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/health")
def health() -> dict:
    return {"health": "healthy"}


@app.post("/api/v1/legal/question", response_model=LegalQuestionResponse)
def legal_question(payload: LegalQuestionRequest) -> LegalQuestionResponse:
    return build_legal_response(payload)


@app.post("/api/v1/legal/instant-solve", response_model=InstantSolveResponse)
def instant_solve(payload: InstantSolveRequest) -> InstantSolveResponse:
    state = normalize_state(payload.state)
    inferred_stage = infer_stage(payload.question)
    inferred_court_level = infer_court_level(payload.question)
    inferred_district = infer_district_from_question(state, payload.question)
    inferred_template_type = infer_template_type(payload.question, inferred_stage)

    full_result = build_legal_response(
        LegalQuestionRequest(
            question=payload.question,
            court_level=inferred_court_level,
            state=state,
            stage=inferred_stage,
            district=inferred_district,
            response_language=payload.response_language,
            template_type=inferred_template_type,
        )
    )

    result_dict = full_result.model_dump()
    return InstantSolveResponse(
        disclaimer=full_result.disclaimer,
        interpreted_issue=full_result.interpreted_issue,
        inferred_stage=inferred_stage,
        inferred_court_level=inferred_court_level,
        inferred_district=inferred_district,
        inferred_template_type=inferred_template_type,
        urgency_level=full_result.urgency_level,
        one_shot_summary=build_one_shot_summary(result_dict),
        top_actions=pick_top_actions(full_result.action_window_24h, limit=3),
        draft_preview=pick_draft_preview(result_dict),
        confidence=full_result.confidence,
        full_result=full_result,
    )


@app.post("/api/v1/fir/analyze", response_model=FIRAnalysisResponse)
async def analyze_fir(state: str = Form("telangana"), file: UploadFile = File(...)) -> FIRAnalysisResponse:
    data = await file.read()
    extracted_text = fir_analyzer.extract_text(file.filename or "uploaded_file", data)

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Unsupported or empty file. Upload .txt, .docx, .pdf, or image (.png/.jpg/.jpeg/.bmp/.tiff).",
        )

    analysis = fir_analyzer.analyze(extracted_text, state=normalize_state(state))
    return FIRAnalysisResponse(
        disclaimer="AI legal research assistant output. Final legal strategy must be reviewed by an enrolled advocate.",
        extracted_sections=analysis["extracted_sections"],
        red_flags=analysis["red_flags"],
        procedural_gaps=analysis["procedural_gaps"],
        suggested_next_steps=analysis["suggested_next_steps"],
        precedent_hints=analysis["precedent_hints"],
    )


@app.post("/api/v1/cases", response_model=CaseResponse)
def create_case(payload: CaseCreateRequest) -> CaseResponse:
    created = case_history_service.create_case(payload.model_dump())
    return CaseResponse(**{**created, "created_at": str(created["created_at"])})


@app.get("/api/v1/cases", response_model=list[CaseResponse])
def list_cases(limit: int = 20) -> list[CaseResponse]:
    cases = case_history_service.list_cases(limit=limit)
    return [CaseResponse(**{**item, "created_at": str(item["created_at"])}) for item in cases]


@app.get("/api/v1/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: int) -> CaseResponse:
    case = case_history_service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return CaseResponse(**{**case, "created_at": str(case["created_at"])})


@app.put("/api/v1/cases/{case_id}", response_model=CaseResponse)
def update_case(case_id: int, payload: CaseUpdateRequest) -> CaseResponse:
    updated = case_history_service.update_case(case_id, payload.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")

    return CaseResponse(**{**updated, "created_at": str(updated["created_at"])})


@app.delete("/api/v1/cases/{case_id}", response_model=DeleteResponse)
def delete_case(case_id: int) -> DeleteResponse:
    deleted = case_history_service.delete_case(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")

    return DeleteResponse(status="success", message=f"Case {case_id} deleted")


@app.post("/api/v1/precedents/search", response_model=PrecedentSearchResponse)
def search_precedents(payload: PrecedentSearchRequest) -> PrecedentSearchResponse:
    state = normalize_state(payload.state)
    results = citation_corpus_service.search(payload.query, state=state, limit=payload.limit)
    return PrecedentSearchResponse(query=payload.query, results=results)


@app.get("/api/v1/admin/corpus/status", response_model=CorpusStatusResponse)
def corpus_status() -> CorpusStatusResponse:
    counts = legal_data_service.corpus_counts()
    return CorpusStatusResponse(
        supported_states=["andhra pradesh", "telangana"],
        statutes=counts["statutes"],
        precedents=counts["precedents"],
    )


@app.post("/api/v1/admin/ingest/statutes", response_model=IngestResponse)
async def ingest_statutes_csv(file: UploadFile = File(...)) -> IngestResponse:
    payload = await file.read()
    text = payload.decode("utf-8", errors="ignore")
    inserted = legal_data_service.load_statutes_csv(text)
    return IngestResponse(
        status="success",
        message="Statutes CSV processed",
        inserted=inserted,
    )


@app.post("/api/v1/admin/ingest/precedents", response_model=IngestResponse)
async def ingest_precedents_csv(file: UploadFile = File(...)) -> IngestResponse:
    payload = await file.read()
    text = payload.decode("utf-8", errors="ignore")
    inserted = legal_data_service.load_precedents_csv(text)
    return IngestResponse(
        status="success",
        message="Precedents CSV processed",
        inserted=inserted,
    )


@app.post("/api/v1/admin/ingest/public-urls", response_model=PublicIngestResponse)
def ingest_public_urls(payload: PublicIngestRequest) -> PublicIngestResponse:
    state = normalize_state(payload.state)
    if payload.document_type != "precedent":
        raise HTTPException(status_code=400, detail="Currently supported document_type: precedent")

    parsed, failed = public_ingestion_service.parse_urls(payload.urls)
    records = [
        {
            "state": state,
            "title": item["title"],
            "citation": item["source_url"],
            "court": "Public Source",
            "year": None,
            "topics": ["public-source", state],
            "snippet": item["snippet"],
            "source_url": item["source_url"],
        }
        for item in parsed
    ]
    inserted = legal_data_service.upsert_precedent_records(records)

    return PublicIngestResponse(
        status="success",
        message="Public URLs processed",
        attempted=len(payload.urls),
        inserted=inserted,
        failed_urls=failed,
    )


@app.get("/api/v1/admin/scheduler/status")
def scheduler_status() -> dict:
    return daily_scheduler.status()


@app.post("/api/v1/admin/scheduler/run-once")
def scheduler_run_once() -> dict:
    result = daily_scheduler.run_once()
    return {
        "status": "success",
        **result,
    }


@app.get("/api/v1/admin/scheduler/runs")
def scheduler_runs(limit: int = 30) -> dict:
    rows = legal_data_service.list_scheduler_runs(limit=limit)
    return {
        "count": len(rows),
        "runs": rows,
    }


@app.get("/api/v1/admin/data-quality")
def data_quality_dashboard(capture_snapshot: bool = False) -> dict:
    return legal_data_service.data_quality_summary(capture_snapshot=capture_snapshot, source="admin_dashboard")


@app.get("/api/v1/admin/data-quality/history")
def data_quality_history(limit: int = 30) -> dict:
    rows = legal_data_service.list_data_quality_history(limit=limit)
    normalized_rows: list[dict] = []
    for row in rows:
        captured = row.get("captured_at")
        trusted_pct = row.get("trusted_source_pct")
        high_quality_pct = row.get("high_quality_pct")
        normalized_rows.append(
            {
                **row,
                "captured_at": captured.isoformat() if hasattr(captured, "isoformat") else captured,
                "trusted_source_pct": float(trusted_pct) if trusted_pct is not None else 0.0,
                "high_quality_pct": float(high_quality_pct) if high_quality_pct is not None else 0.0,
            }
        )

    return {
        "count": len(normalized_rows),
        "history": normalized_rows,
    }
