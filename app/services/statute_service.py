from .legal_data_service import LegalDataService


class StatuteService:
    def __init__(self) -> None:
        self.legal_data = LegalDataService()

    def map_from_text(self, text: str, state: str) -> list[dict]:
        return self.legal_data.fetch_statute_matches(text=text, state=state, limit=10)
