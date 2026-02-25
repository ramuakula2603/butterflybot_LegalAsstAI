from .legal_data_service import LegalDataService


class PrecedentService:
    def __init__(self) -> None:
        self.legal_data = LegalDataService()

    def search(self, query: str, state: str, limit: int = 3) -> list[dict]:
        return self.legal_data.fetch_precedent_matches(query_text=query, state=state, limit=limit)
