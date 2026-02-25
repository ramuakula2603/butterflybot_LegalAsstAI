from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class ParsedLegalPage:
    title: str
    snippet: str
    source_url: str


class PublicIngestionService:
    def __init__(self) -> None:
        self.trusted_domains = {
            "indiankanoon.org",
            "indiacode.nic.in",
            "sci.gov.in",
            "tshc.gov.in",
            "hc.ap.nic.in",
            "districts.ecourts.gov.in",
        }

    def _is_trusted_url(self, url: str) -> bool:
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False
        if not host:
            return False
        return any(host == domain or host.endswith(f".{domain}") for domain in self.trusted_domains)

    def fetch_page(self, url: str, timeout: int = 20) -> ParsedLegalPage:
        if not self._is_trusted_url(url):
            raise ValueError("Untrusted source domain")

        response = requests.get(url, timeout=timeout, headers={"User-Agent": "ButterflyBot/1.0"})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else ""
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""

        text = " ".join(fragment.strip() for fragment in soup.stripped_strings)
        compact = " ".join(text.split())
        snippet = compact[:3500]

        if not title or title.lower() == "untitled":
            raise ValueError("Low quality page title")
        if len(snippet) < 180:
            raise ValueError("Insufficient page content")

        lowered = snippet.lower()
        if "act/judgment not found" in lowered or "document not found" in lowered:
            raise ValueError("Invalid legal document page")

        return ParsedLegalPage(title=title, snippet=snippet, source_url=url)

    def parse_urls(self, urls: list[str]) -> tuple[list[dict], list[str]]:
        parsed: list[dict] = []
        failed: list[str] = []

        for url in urls:
            try:
                page = self.fetch_page(url)
                parsed.append({
                    "title": page.title,
                    "snippet": page.snippet,
                    "source_url": page.source_url,
                })
            except Exception:
                failed.append(url)

        return parsed, failed
