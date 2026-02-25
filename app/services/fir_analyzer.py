import re
from io import BytesIO

from docx import Document
from pypdf import PdfReader

from .ocr_service import ocr_image_bytes, ocr_pdf_bytes
from .precedent_service import PrecedentService
from .statute_service import StatuteService
from .strategy_service import build_strategy

SECTION_PATTERN = re.compile(r"\b(IPC|BNS|CrPC|BNSS|Evidence|BSA)\s*-?\s*(\d+[A-Z]?)\b", re.IGNORECASE)


class FIRAnalyzer:
    def __init__(self) -> None:
        self.statutes = StatuteService()
        self.precedents = PrecedentService()

    def extract_text(self, filename: str, payload: bytes) -> str:
        lower_name = filename.lower()

        if lower_name.endswith(".txt"):
            return payload.decode("utf-8", errors="ignore")

        if lower_name.endswith(".docx"):
            doc = Document(BytesIO(payload))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text)

        if lower_name.endswith(".pdf"):
            reader = PdfReader(BytesIO(payload))
            pages = [page.extract_text() or "" for page in reader.pages]
            extracted = "\n".join(pages)
            if len(extracted.strip()) >= 120:
                return extracted

            try:
                ocr_text = ocr_pdf_bytes(payload)
                return ocr_text if ocr_text.strip() else extracted
            except Exception:
                return extracted

        if lower_name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")):
            try:
                return ocr_image_bytes(payload)
            except Exception:
                return ""

        return ""

    def analyze(self, text: str, state: str) -> dict:
        normalized = text.lower()

        extracted_sections = [
            {"code": match.group(1).upper(), "section": match.group(2)}
            for match in SECTION_PATTERN.finditer(text)
        ]

        procedural_gaps = []
        checks = {
            "occurrence date missing": ["date of incident", "date"],
            "occurrence time missing": ["time of incident", "time"],
            "location/jurisdiction details missing": ["place of incident", "police station", "jurisdiction"],
            "witness details sparse": ["witness", "eyewitness"],
            "delay explanation not visible": ["delay", "explained"],
        }

        for gap, keywords in checks.items():
            if not any(keyword in normalized for keyword in keywords):
                procedural_gaps.append(gap)

        red_flags = []
        if "unknown" in normalized and "accused" in normalized:
            red_flags.append("Identity of accused appears uncertain in narrative.")
        if "hearsay" in normalized:
            red_flags.append("Narrative indicates hearsay dependency; credibility challenge may arise.")
        if len(text.split()) < 120:
            red_flags.append("FIR narrative appears unusually brief; factual particulars may be incomplete.")

        mapped_sections = self.statutes.map_from_text(text, state=state)
        precedent_hints = self.precedents.search(text, state=state)
        next_steps = build_strategy(stage="investigation", court_level="trial")

        return {
            "extracted_sections": extracted_sections,
            "mapped_sections": mapped_sections,
            "procedural_gaps": procedural_gaps,
            "red_flags": red_flags,
            "precedent_hints": precedent_hints,
            "suggested_next_steps": next_steps,
        }
