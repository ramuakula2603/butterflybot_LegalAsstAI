def _normalize_template_type(template_type: str, stage: str) -> str:
    requested = (template_type or "auto").strip().lower()
    if requested in {"bail_memo", "notice_reply", "quash_checklist"}:
        return requested

    stage_key = (stage or "").lower()
    if stage_key == "bail":
        return "bail_memo"
    if stage_key == "trial":
        return "quash_checklist"
    return "notice_reply"


def _district_line(district: str) -> str:
    return district.title() if district else "District Court"


def _build_draft_text(
    template_name: str,
    state_label: str,
    district_label: str,
    court_label: str,
    issue: str,
    sections: list[str],
) -> str:
    lines = [
        f"[DRAFT TEMPLATE] {template_name}",
        f"State: {state_label}",
        f"District: {district_label}",
        f"Court Level: {court_label}",
        "",
        "Issue Snapshot:",
        issue,
        "",
        "Proposed Structure:",
    ]

    for idx, section in enumerate(sections, start=1):
        lines.append(f"{idx}. {section}")

    lines += [
        "",
        "Draft Notes:",
        "- Replace placeholders with case-specific facts and dates.",
        "- Attach referenced documents with annexure labels.",
        "- Finalize and vet with enrolled advocate before filing.",
    ]

    return "\n".join(lines)


def build_filing_templates(
    question: str,
    state: str,
    district: str,
    court_level: str,
    stage: str,
    template_type: str,
) -> list[dict]:
    resolved_type = _normalize_template_type(template_type, stage)
    district_label = _district_line(district)
    state_label = "Telangana" if state == "telangana" else "Andhra Pradesh"
    court_label = (court_level or "trial").title()
    issue = (question or "").strip()

    common_meta = {
        "state": state_label,
        "district": district_label,
        "court_level": court_label,
        "issue_snapshot": issue,
    }

    templates = {
        "bail_memo": {
            "template_name": "Anticipatory/Regular Bail Memo",
            "purpose": "Court-ready structure to present bail grounds and compliance plan.",
            "sections": [
                "Case heading and party details",
                "Brief facts with allegation summary",
                "Grounds: false implication, cooperation, parity, no flight risk",
                "Medical/family/work hardship grounds (if applicable)",
                "Proposed bail conditions and surety readiness",
                "Prayer for interim/final bail relief",
            ],
            "district_notes": [
                f"{district_label}: keep concise chronology and annexure index for first hearing.",
                "Attach identity/address proofs and cooperation undertaking.",
                "Keep alternative relief wording ready if strict conditions are suggested.",
            ],
        },
        "notice_reply": {
            "template_name": "Police Notice Reply Pack",
            "purpose": "Structured response to notice while preserving rights and evidence trail.",
            "sections": [
                "Reference to notice number/date and receiving details",
                "Short factual response with no self-incriminating overreach",
                "Request for complete allegations/document copies relied upon",
                "Evidence-preservation request (CCTV/CDR/device logs)",
                "Declaration of cooperation through advocate",
                "List of enclosed documents and acknowledgement request",
            ],
            "district_notes": [
                f"{district_label}: submit written acknowledgement copy and preserve dispatch proof.",
                "Use advocate-signed covering letter and document index.",
                "Track follow-up dates in a compliance log.",
            ],
        },
        "quash_checklist": {
            "template_name": "Quash/Discharge Readiness Checklist",
            "purpose": "Issue-based checklist for maintainability and abuse-of-process arguments.",
            "sections": [
                "Ingredient test: allegation vs legal ingredients table",
                "Delay/mala fide/parallel civil-dispute indicators",
                "Jurisdiction and procedural irregularity points",
                "Precedent matrix with ratio relevance",
                "Annexure quality check (authenticity and legibility)",
                "Relief framing: primary and alternative prayers",
            ],
            "district_notes": [
                f"{district_label}: prepare short note on maintainability and urgency for admission stage.",
                "Keep contradiction chart between complaint, FIR, and record material.",
                "Ensure all annexures are paginated and cross-referenced in synopsis.",
            ],
        },
    }

    selected = templates[resolved_type]
    draft_text = _build_draft_text(
        template_name=selected["template_name"],
        state_label=state_label,
        district_label=district_label,
        court_label=court_label,
        issue=issue,
        sections=selected["sections"],
    )
    return [
        {
            **common_meta,
            "template_type": resolved_type,
            "template_name": selected["template_name"],
            "purpose": selected["purpose"],
            "sections": selected["sections"],
            "district_notes": selected["district_notes"],
            "draft_text": draft_text,
        }
    ]
