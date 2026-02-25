def build_strategy(stage: str, court_level: str) -> list[str]:
    base_steps = [
        "Create a fact chronology with exact date/time/place and supporting proof.",
        "Map each allegation element to evidence available vs missing.",
        "Prepare argument notes with cited statutes and precedent ratio.",
    ]

    stage_map = {
        "investigation": [
            "Review FIR for missing ingredients and contradictory allegations.",
            "Seek preservation of CCTV/CDR/electronic evidence immediately.",
            "Evaluate anticipatory bail or regular bail strategy as applicable.",
        ],
        "bail": [
            "Compile parity grounds, antecedents, and flight-risk rebuttal.",
            "Highlight weak prima facie case and procedural irregularities.",
            "Propose workable bail conditions to satisfy court concerns.",
        ],
        "trial": [
            "Prepare issue-wise cross-examination plan for key witnesses.",
            "Challenge admissibility defects (including electronic evidence compliance).",
            "Frame final arguments around burden of proof and precedent principles.",
        ],
    }

    level_note = f"Customize filing format and relief language for {court_level} court practice."
    return stage_map.get(stage.lower(), stage_map["investigation"]) + base_steps + [level_note]


def document_checklist(case_type: str = "criminal") -> list[str]:
    criminal = [
        "Certified/true copy of FIR and all complaint annexures",
        "Arrest memo, remand papers, and bail order history (if any)",
        "Case diary extracts/order sheets available on record",
        "Medical/FSL/electronic evidence documents with certificate requirements",
        "Prior related litigation/orders involving same parties",
    ]

    civil = [
        "Plaint, written statement, and amendment history",
        "Cause of action timeline with supporting contracts/records",
        "Interim applications and previous interim orders",
        "Document admission/denial chart",
        "Valuation, limitation, and jurisdiction materials",
    ]

    return civil if case_type.lower() == "civil" else criminal
