import os

from openai import OpenAI


class LLMFallbackService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("LEGAL_LLM_MODEL", "gpt-4.1-mini")

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def generate(self, question: str, state: str) -> dict | None:
        if not self.is_enabled():
            return None

        client = OpenAI(api_key=self.api_key)
        prompt = (
            "You are an Indian legal research assistant. "
            "Focus on criminal and civil procedure relevance for the given state. "
            "Return concise JSON with keys: summary, possible_sections, practical_steps, caution. "
            "Do not claim guaranteed outcomes. "
            f"State: {state}. Question: {question}"
        )

        response = client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
        )
        text = response.output_text if hasattr(response, "output_text") else ""
        return {"model": self.model, "raw_text": text}
