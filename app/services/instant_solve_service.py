from app.services.citizen_guidance_service import resolve_district


def infer_stage(question: str) -> str:
    text = (question or "").lower()
    if any(token in text for token in ["bail", "anticipatory", "arrest", "custody", "nbw"]):
        return "bail"
    if any(token in text for token in ["trial", "evidence", "witness", "cross"]):
        return "trial"
    return "investigation"


def infer_court_level(question: str) -> str:
    text = (question or "").lower()
    if "supreme" in text:
        return "supreme"
    if "high court" in text or "hc" in text:
        return "high"
    if "sessions" in text:
        return "sessions"
    return "trial"


def infer_template_type(question: str, stage: str) -> str:
    text = (question or "").lower()
    if "notice" in text or "reply" in text:
        return "notice_reply"
    if "quash" in text or "482" in text or "discharge" in text:
        return "quash_checklist"
    if stage == "bail":
        return "bail_memo"
    return "auto"


def infer_district_from_question(state: str, question: str) -> str:
    text = (question or "").lower()
    district_hints = {
        "hyderabad": "hyderabad",
        "rangareddy": "rangareddy",
        "ranga reddy": "rangareddy",
        "vijayawada": "vijayawada",
        "visakhapatnam": "visakhapatnam",
        "vizag": "visakhapatnam",
    }

    for token, district in district_hints.items():
        if token in text:
            return resolve_district(state, district)

    return resolve_district(state, "")


def build_one_shot_summary(result: dict) -> str:
    urgency = str(result.get("urgency_level", "medium")).upper()
    stage = result.get("interpreted_issue", "")
    sections = result.get("mapped_sections") or []
    precedents = result.get("citation_hits") or []

    section_note = f"{len(sections)} section mappings" if sections else "no direct section mapping"
    precedent_note = f"{len(precedents)} precedent/citation hits" if precedents else "no precedent hit yet"

    return (
        f"Priority {urgency}. Quick view: {section_note}, {precedent_note}. "
        "Immediate focus is evidence preservation, procedural protection, and filing-ready draft execution. "
        f"Issue: {stage}"
    )


def pick_top_actions(actions: list[str], limit: int = 3) -> list[str]:
    return (actions or [])[:limit]


def pick_draft_preview(result: dict) -> str:
    templates = result.get("filing_templates") or []
    if not templates:
        return "No draft template generated."
    first = templates[0] or {}
    return first.get("draft_text", "No draft template generated.")
