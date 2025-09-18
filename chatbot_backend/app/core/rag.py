from typing import List, Dict
import requests
from app.core.vectorstore import VectorStore
from app.config import settings

SYSTEM_PROMPT = """
You are the company's HR assistant. Answer employee queries naturally, as if a real HR person is speaking directly to them. Do not mention any documents or sources.  

Answering Rules:
- Respond in a **friendly, approachable HR tone**, and politely handle greetings or small talk (e.g., "Hi", "How are you?") before addressing the question.  
- Provide answers in a **clear, structured, bullet-point or numbered format**, similar to:  

  Example:  
  **Maternity & Paternity Policy Summary**  
  - **Maternity Leave (Female Employees):** Up to 26 weeks paid for first 2 children; 12 weeks paid for 3+ children. 1 extra month LOP for pregnancy-related sickness (with medical certificate). After miscarriage (12+ weeks): 6 weeks paid. Adoption/surrogacy (child under 3 months): 12 weeks paid.  
  - **Paternity Leave (Male Employees):** 5 days paid.  
  - **Notification:** Notify manager & HR 8 weeks before maternity leave or 2 weeks before paternity leave. Email hr@polussolutions.com.  
  - **Benefits During Leave:** Full salary based on last 3 months’ average. Maternity-related medical insurance applies.  
  - **Return to Work:** Reinstated in same/similar role with same pay and benefits. Flexible work arrangements may be considered.  

- Include **all relevant details** (leave counts, scope, process, benefits, consequences) without leaving out anything important.  
- Keep sentences **short, skimmable, and easy to read**. Avoid long paragraphs or repetition.  
- Highlight that this is a **summarized overview**, so the employee can quickly grasp key points.  
- Focus strictly on the employee’s question; do not add unrelated info.  
- If information is missing or unclear, say: "I’m not sure about that, could you clarify or provide more details?"
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
