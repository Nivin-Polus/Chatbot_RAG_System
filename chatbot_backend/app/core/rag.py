from typing import List, Dict
import requests
from app.core.vectorstore import VectorStore
from app.config import settings

SYSTEM_PROMPT = """
You are a corporate knowledge assistant. Your job is to answer strictly based on the provided company documents.

Answering Rules:
- Provide a **clear, summarized answer** (3–6 bullet points or numbered sections).
- Include **all relevant details** (definitions, leave counts, scope, process, consequences).
- Do **not** copy long paragraphs. Compress into shorter, direct sentences.
- Avoid repetition and unnecessary wording.
- The answer should be **short enough to skim quickly**, but **complete enough** that no critical information is missing.
- If info is missing, say: 
  "I wasn’t able to retrieve a confident answer, please refine your question."
"""

class RAG:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

        # Claude/LLM settings
        self.api_key = settings.CLAUDE_API_KEY
        self.endpoint = "https://api.anthropic.com/v1/messages"
        self.model = getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307")
        self.max_tokens = getattr(settings, "CLAUDE_MAX_TOKENS", 1000)
        self.temperature = getattr(settings, "CLAUDE_TEMPERATURE", 0.0)

    def retrieve_chunks(self, query: str, top_k: int = 5) -> List[str]:
        """Search vector DB and return top matching chunks."""
        results = self.vector_store.search(query, top_k=top_k)
        return [r["payload"].get("text", "") for r in results]

    def call_ai(self, prompt: str) -> str:
        """Call Claude (or configured LLM)."""
        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            return data.get("content", [{}])[0].get("text", "").strip()
        except Exception as e:
            print(f"Claude API Error: {e}")
            return "I wasn’t able to retrieve a confident answer, please refine your question."

    def answer(self, query: str, top_k: int = 5) -> str:
        """Main pipeline: retrieve → medium-detailed answer."""
        chunks = self.retrieve_chunks(query, top_k=top_k)
        if not chunks:
            return "I wasn’t able to retrieve a confident answer, please refine your question."

        # Build medium-length answer
        context = "\n---\n".join(chunks)
        prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {query}\nAnswer:"
        answer = self.call_ai(prompt)

        return answer
