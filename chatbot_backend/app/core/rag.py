from typing import List, Dict
import requests
from app.core.vectorstore import VectorStore
from app.config import settings

# Default system prompt - can be overridden via environment variable or config
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant for a knowledge base system. Your role is to respond naturally and conversationally based on the provided context from uploaded documents.

Answering Rules:
- **Tone:** Professional, clear, and approachable. Begin with a polite acknowledgment before answering the query.
- **Clarity:** Keep responses short, precise, and easy to skim. Use bullet points or numbered lists where helpful. Avoid long paragraphs.
- **Relevance:** Focus strictly on the question asked. Do not add unrelated or extra details.
- **Out-of-Scope Queries:** If the question is not covered in the knowledge base, respond with:
  "I don't have that information in the current knowledge base. Please contact the system administrator for further details."
- **Information Boundaries:** Never guess or provide assumptions. Only use information explicitly available in the knowledge base.
- **Missing/Unclear Questions:** If a query is unclear, say:
  "I'm not sure what you mean. Could you clarify or provide more details?"
- **Context Usage:** Use the provided context from uploaded documents to answer questions accurately.
- **Goal:** Provide accurate, professional, and helpful responses based on the available knowledge base content."""



class RAG:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

        # Claude/LLM settings
        self.api_key = settings.CLAUDE_API_KEY
        self.endpoint = getattr(settings, "CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
        self.model = getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307")
        self.max_tokens = getattr(settings, "CLAUDE_MAX_TOKENS", 1000)
        self.temperature = getattr(settings, "CLAUDE_TEMPERATURE", 0.0)
        self.system_prompt = getattr(settings, "SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

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
            return "I wasn't able to retrieve a confident answer, please refine your question."

        # Build medium-length answer
        context = "\n---\n".join(chunks)
        prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nQuestion: {query}\nAnswer:"
        answer = self.call_ai(prompt)

        return answer

    def answer_with_context(self, query: str, conversation_history: List, top_k: int = 5) -> str:
        """Main pipeline with conversation context: retrieve → contextual answer."""
        chunks = self.retrieve_chunks(query, top_k=top_k)
        if not chunks:
            return "I wasn't able to retrieve a confident answer, please refine your question."

        # Build conversation context
        conversation_context = ""
        if conversation_history:
            conversation_context = "\n\nPrevious Conversation:\n"
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                # Handle both Pydantic objects and dictionaries
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    # Pydantic object
                    role = "Human" if msg.role == "user" else "Assistant"
                    content = msg.content
                else:
                    # Dictionary
                    role = "Human" if msg.get("role") == "user" else "Assistant"
                    content = msg.get("content", "")
                
                conversation_context += f"{role}: {content}\n"
            conversation_context += "\n"

        # Build contextual answer
        context = "\n---\n".join(chunks)
        prompt = f"{self.system_prompt}\n\nContext:\n{context}{conversation_context}\nCurrent Question: {query}\nAnswer:"
        answer = self.call_ai(prompt)

        return answer
