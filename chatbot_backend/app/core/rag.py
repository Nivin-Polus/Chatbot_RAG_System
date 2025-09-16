# app/core/rag.py

from typing import List
import requests
from app.core.vectorstore import VectorStore
from app.config import settings

SYSTEM_PROMPT = (
    "Answer strictly based on provided documents. "
    "If unsure, respond: 'I wasn’t able to retrieve a confident answer, please refine your question.'"
)

class RAG:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

        # Load Claude/AI settings from config
        self.api_key = settings.CLAUDE_API_KEY
        self.endpoint = getattr(settings, "CLAUDE_API_URL", "https://api.anthropic.com/v1/complete")
        self.model = getattr(settings, "CLAUDE_MODEL", "claude-v1")
        self.max_tokens = getattr(settings, "CLAUDE_MAX_TOKENS", 1000)
        self.temperature = getattr(settings, "CLAUDE_TEMPERATURE", 0.0)

    def retrieve_chunks(self, query: str, top_k: int = 5) -> List[str]:
        results = self.vector_store.search(query, top_k=top_k)
        return [r["payload"].get("text", "") for r in results]

    def generate_prompt(self, query: str, chunks: List[str]) -> str:
        context = "\n---\n".join(chunks)
        prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {query}\nAnswer:"
        return prompt

    def ask_AI(self, prompt: str) -> str:
        """
        Call Claude (or configured LLM). Fallback if fails.
        """
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": self.max_tokens,
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
            return "I wasn't able to retrieve a confident answer, please refine your question."

    def answer(self, query: str, top_k: int = 5) -> str:
        chunks = self.retrieve_chunks(query, top_k=top_k)
        if not chunks:
            return "I wasn’t able to retrieve a confident answer, please refine your question."
        prompt = self.generate_prompt(query, chunks)
        answer = self.ask_AI(prompt)
        return answer
