def detect_urgency(question: str, stage: str) -> str:
    text = (question or "").lower()
    stage_key = (stage or "").lower()

    high_triggers = [
        "arrest",
        "custody",
        "warrant",
        "non-bailable",
        "nbw",
        "lookout",
        "seizure",
        "notice",
    ]

    medium_triggers = [
        "fir",
        "cheating",
        "threat",
        "cyber fraud",
        "forgery",
        "summons",
    ]

    if stage_key == "bail" or any(word in text for word in high_triggers):
        return "high"
    if any(word in text for word in medium_triggers):
        return "medium"
    return "low"


def build_action_window_24h(stage: str, urgency: str) -> list[str]:
    stage_key = (stage or "").lower()

    baseline = [
        "Create a one-page incident timeline with exact dates, places, and persons involved.",
        "Preserve all digital evidence (messages, call logs, emails, CCTV requests) with backups.",
        "Prepare an advocate briefing note with facts, allegations, and immediate relief required.",
    ]

    stage_actions = {
        "investigation": [
            "Collect FIR/complaint copy and verify whether essential allegations are clearly stated.",
            "Submit a written representation to preserve CCTV/CDR and other time-sensitive evidence.",
        ],
        "bail": [
            "Compile identity, local-address, and cooperation documents for bail readiness.",
            "Draft grounds on false implication, parity, and no flight risk with supporting records.",
        ],
        "trial": [
            "Prepare witness-wise contradiction sheet from complaint, FIR, and statements available.",
            "List admissibility objections for electronic and documentary evidence.",
        ],
    }

    urgent_addons = [
        "If arrest risk is immediate, contact advocate now and keep anticipatory/regular bail papers ready.",
        "Avoid informal police statements without legal consultation; insist on documented process.",
    ]

    actions = stage_actions.get(stage_key, stage_actions["investigation"]) + baseline
    if urgency == "high":
        actions = urgent_addons + actions
    return actions


def build_local_process_map(state: str, stage: str, court_level: str) -> list[str]:
    state_label = "Telangana" if state == "telangana" else "Andhra Pradesh"
    stage_key = (stage or "").lower()

    common = [
        f"State focus: {state_label} procedural flow and filing expectations.",
        f"Court track: {court_level.title()} court drafting style and hearing preparation.",
    ]

    stage_map = {
        "investigation": [
            "Police stage: FIR/notice response, evidence-preservation requests, and representation drafting.",
            "Pre-filing stage: identify whether bail, quash, or complaint-side escalation is suitable.",
        ],
        "bail": [
            "Bail stage: document package, surety readiness, and condition-compliance plan.",
            "Hearing stage: address prosecution objections with fact chronology and precedent points.",
        ],
        "trial": [
            "Trial stage: witness strategy, contradiction matrix, and admissibility objections.",
            "Argument stage: map burden-of-proof gaps and relief-focused final submissions.",
        ],
    }

    return common + stage_map.get(stage_key, stage_map["investigation"])


def resolve_district(state: str, district: str) -> str:
    normalized = (district or "").strip().lower()
    if not normalized:
        return "hyderabad" if state == "telangana" else "vijayawada"

    aliases = {
        "vizag": "visakhapatnam",
        "visakha": "visakhapatnam",
        "hyd": "hyderabad",
        "rr": "rangareddy",
        "ranga reddy": "rangareddy",
    }
    return aliases.get(normalized, normalized)


def build_district_playbook(state: str, district: str, stage: str, court_level: str) -> list[str]:
    resolved = resolve_district(state, district)
    stage_key = (stage or "").lower()
    level = (court_level or "trial").title()

    district_map = {
        "hyderabad": [
            "Use concise, issue-first filings; keep chronology and annexure index court-ready.",
            "For urgent relief, prepare same-day mention note with short factual matrix.",
            "Carry clean paper-book with section markers for faster bench reference.",
        ],
        "rangareddy": [
            "Prioritize procedural compliance docs (service proof, notice copies, acknowledgements).",
            "Keep witness/event timeline aligned to complaint and investigation records.",
            "Prepare practical condition-compliance plan for interim relief hearings.",
        ],
        "vijayawada": [
            "File with strong maintainability framing and relief prayer clarity.",
            "Bundle supporting precedents in short-note format with ratio in 2-3 lines each.",
            "Prepare alternative relief wording to handle bench concerns during first hearing.",
        ],
        "visakhapatnam": [
            "Focus on documentary consistency and authenticity trail in annexures.",
            "Keep electronic evidence note ready with source, custody, and certificate status.",
            "Use hearing checklist with objections-response matrix for each allegation point.",
        ],
    }

    stage_tips = {
        "investigation": "Immediate step: preserve volatile evidence and file representation without delay.",
        "bail": "Immediate step: prepare surety/profile packet and rebut arrest-necessity grounds.",
        "trial": "Immediate step: maintain witness contradiction chart and exhibit admissibility tracker.",
    }

    fallback = [
        "Adopt district court filing norms and keep a concise fact-first draft.",
        "Use a hearing-ready checklist with documents, precedents, and relief alternatives.",
        "Maintain daily case-log for orders, compliance tasks, and next hearing objective.",
    ]

    district_steps = district_map.get(resolved, fallback)
    return [
        f"District focus: {resolved.title()} | Court level: {level}",
        *district_steps,
        stage_tips.get(stage_key, stage_tips["investigation"]),
    ]


def extract_risk_signals(question: str) -> list[str]:
    text = (question or "").lower()
    signals: list[str] = []

    mapping = {
        "arrest": "Possible arrest exposure; prioritize bail-readiness and legal representation.",
        "nbw": "Non-bailable warrant risk indicated; verify warrant status urgently.",
        "warrant": "Warrant-related risk indicated; validate case status and court directions.",
        "seizure": "Property/device seizure risk; prepare ownership and relevance documentation.",
        "cheating": "Cheating allegation may involve intent analysis; preserve transactional records.",
        "forgery": "Forgery-related allegation may require document-authenticity defense planning.",
        "cyber": "Cyber evidence volatility risk; preserve logs, device records, and metadata quickly.",
    }

    for token, message in mapping.items():
        if token in text:
            signals.append(message)

    return signals or ["No immediate high-risk keyword found; continue evidence and timeline preparation."]


def build_citizen_brief(question: str, state: str, stage: str, urgency: str, response_language: str = "english") -> dict:
    state_telugu = "తెలంగాణ" if state == "telangana" else "ఆంధ్రప్రదేశ్"
    stage_telugu_map = {
        "investigation": "దర్యాప్తు దశ",
        "bail": "బెయిల్ దశ",
        "trial": "విచారణ దశ",
    }
    stage_telugu = stage_telugu_map.get((stage or "").lower(), "దర్యాప్తు దశ")

    english = (
        f"Your issue is being treated as a {urgency.upper()} priority for {state.title()} at {stage} stage. "
        "First secure documents and evidence, then move with advocate-reviewed filing strategy."
    )

    telugu = (
        f"మీ సమస్యను {state_telugu}లో {stage_telugu}లో {urgency.upper()} ప్రాధాన్యతగా పరిగణిస్తున్నాం. "
        "మొదట ఆధారాలు, పత్రాలు భద్రపరచండి; తర్వాత న్యాయవాది సలహాతో తదుపరి చర్యలు తీసుకోండి."
    )

    language = (response_language or "english").lower()
    payload = {"question_snapshot": question.strip()}

    if language == "telugu":
        payload["primary"] = telugu
        payload["supporting_english"] = english
    elif language == "bilingual":
        payload["english"] = english
        payload["telugu"] = telugu
    else:
        payload["primary"] = english
        payload["supporting_telugu"] = telugu

    return payload
