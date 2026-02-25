import re

from .legal_data_service import LegalDataService

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class CitationCorpusService:
    def __init__(self) -> None:
        self.legal_data = LegalDataService()

    def _tokenize(self, text: str) -> set[str]:
        return {token.lower() for token in TOKEN_PATTERN.findall(text) if len(token) > 2}

    def search(self, query: str, state: str, limit: int = 5) -> list[dict]:
        query_tokens = self._tokenize(query)
        scored: list[tuple[float, dict]] = []

        records = self.legal_data.fetch_precedent_matches(query_text=query, state=state, limit=100)

        for record in records:
            text_blob = " ".join([
                record.get("title", ""),
                record.get("citation", ""),
                " ".join(record.get("topics", [])),
                record.get("snippet", ""),
            ])
            doc_tokens = self._tokenize(text_blob)
            overlap = query_tokens.intersection(doc_tokens)
            score = (len(overlap) / max(len(query_tokens), 1)) if query_tokens else 0.0

            scored.append(
                (
                    score,
                    {
                        **record,
                        "score": round(score, 3),
                        "matched_terms": sorted(overlap),
                    },
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        top = [item for score, item in scored if score > 0][:limit]
        return top
