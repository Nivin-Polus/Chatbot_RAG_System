from typing import List, Dict, Optional
import requests
from sqlalchemy.orm import Session
from app.config import settings
from app.models.system_prompt import SystemPrompt
from app.models.collection import Collection
from app.core.database import get_db

# Default system prompt - can be overridden via environment variable or config
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant for a knowledge base system. Your role is to respond naturally and conversationally based on the provided context from uploaded documents.

Answering Rules:
- **Tone:** Professional, clear, and approachable. Begin with a polite acknowledgment before answering the query.
- **Clarity:** Keep responses short, precise, and easy to skim. Use bullet points or numbered lists where helpful. Avoid long paragraphs.
- **Relevance:** Focus strictly on the question asked. Do not add unrelated or extra details.
- **Source Attribution:** ALWAYS include a "Sources:" section at the end listing the specific files you referenced.
- **Out-of-Scope Queries:** If the question is not covered in the knowledge base, respond with:
  "I don't have that information in the current knowledge base. Please contact the system administrator for further details."
- **Information Boundaries:** Never guess or provide assumptions. Only use information explicitly available in the knowledge base.
- **Missing/Unclear Questions:** If a query is unclear, say:
  "I'm not sure what you mean. Could you clarify or provide more details?"
- **Context Usage:** Use the provided context from uploaded documents to answer questions accurately.
- **Goal:** Provide accurate, professional, and helpful responses with clear source attribution so users can verify information."""



class RAG:
    def __init__(self, db_session: Session = None):
        self.db_session = db_session
        self._vector_store = None

        # Claude/LLM settings
        self.api_key = settings.CLAUDE_API_KEY
        self.endpoint = getattr(settings, "CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
        
        # Default settings (can be overridden by database prompts)
        self.default_model = getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307")
        self.default_max_tokens = getattr(settings, "CLAUDE_MAX_TOKENS", 4000)
        self.default_temperature = getattr(settings, "CLAUDE_TEMPERATURE", 0.7)
        self.default_system_prompt = getattr(settings, "SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

    @property
    def vector_store(self):
        """Lazily initialize vector store to avoid PyO3 issues during module import"""
        if self._vector_store is None:
            from app.core.vectorstore import VectorStore
            self._vector_store = VectorStore(settings.VECTOR_DB_URL)
        return self._vector_store

    # ------------------------------------------------------------------
    # Small talk helpers
    # ------------------------------------------------------------------
    def _is_small_talk(self, query: str) -> bool:
        """Simple heuristic to skip the RAG pipeline for casual greetings."""
        if not query:
            return False

        normalized = query.strip().lower()
        small_talk_phrases = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening",
            "good afternoon",
            "how are you",
            "what's up",
            "hi there",
            "hello there",
        }

        return normalized in small_talk_phrases

    def _handle_small_talk(self, query: str) -> str:
        """Return a friendly response for small talk interactions."""
        return (
            "Hello! I'm here to help with questions about your knowledge base documents. "
            "Let me know what you'd like to learn or explore."
        )

    def get_prompt_for_collection(self, collection_id: str) -> Optional[SystemPrompt]:
        """Get the active prompt for a specific collection from database"""
        if not self.db_session or not collection_id:
            return None
        
        try:
            # First try to get the default prompt for this collection
            prompt = self.db_session.query(SystemPrompt).filter(
                SystemPrompt.collection_id == collection_id,
                SystemPrompt.is_active == True,
                SystemPrompt.is_default == True
            ).first()
            
            # If no default prompt, get any active prompt for this collection
            if not prompt:
                prompt = self.db_session.query(SystemPrompt).filter(
                    SystemPrompt.collection_id == collection_id,
                    SystemPrompt.is_active == True
                ).first()
            
            return prompt
        except Exception as e:
            print(f"Error getting prompt for collection {collection_id}: {e}")
            return None

    def retrieve_chunks(self, query: str, top_k: int = 5, collection_id: str = None, allowed_file_ids: Optional[set] = None) -> List[Dict]:
        """Search vector DB and return top matching chunks with metadata.
        Optionally restrict results to specific file_ids (allowed_file_ids).
        """
        results = self.vector_store.search(query, top_k=top_k, collection_id=collection_id)
        chunks_with_sources = []
        for r in results:
            payload = r.get("payload", {})

            if collection_id is not None:
                payload_collection_id = payload.get("collection_id")
                if payload_collection_id is None:
                    # Skip chunks that are not explicitly tagged to avoid cross-collection bleed
                    continue
                if str(payload_collection_id) != str(collection_id):
                    continue
            # Enforce file-level access if provided
            if allowed_file_ids is not None:
                file_id_val = payload.get("file_id")
                if not file_id_val or str(file_id_val) not in allowed_file_ids:
                    continue
            chunks_with_sources.append({
                "text": payload.get("text", ""),
                "file_name": payload.get("file_name", "Unknown File"),
                "file_id": payload.get("file_id", ""),
                "chunk_index": payload.get("chunk_index", 0)
            })
        return chunks_with_sources

    def _resolve_prompt_settings(self, collection_id: Optional[str] = None):
        """Determine system prompt and model configuration for the given collection."""
        db_prompt = None
        if collection_id:
            db_prompt = self.get_prompt_for_collection(collection_id)

        if db_prompt:
            system_prompt = db_prompt.system_prompt
            model = db_prompt.model_name
            max_tokens = db_prompt.max_tokens
            temperature = db_prompt.temperature
        else:
            system_prompt = self.default_system_prompt
            model = self.default_model
            max_tokens = self.default_max_tokens
            temperature = self.default_temperature

        if db_prompt and self.db_session:
            try:
                db_prompt.increment_usage(self.db_session)
            except Exception as e:
                print(f"Error updating prompt usage: {e}")

        return system_prompt, model, max_tokens, temperature

    def call_ai(self, prompt: str, model: str = None, max_tokens: int = None, temperature: float = None) -> str:
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
                    "model": model or self.default_model,
                    "max_tokens": max_tokens or self.default_max_tokens,
                    "temperature": temperature or self.default_temperature,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            return data.get("content", [{}])[0].get("text", "").strip()
        except Exception as e:
            print(f"Claude API Error: {e}")
            return "I wasn't able to retrieve a confident answer, please refine your question."

    def _inject_sources(self, answer: str, source_files: set) -> str:
        """Ensure a single, deduplicated Sources section at the end of the answer.
        If the model already included a Sources section, replace it with our canonical version.
        """
        if not source_files:
            return answer

        import re
        # Remove any existing Sources section (case-insensitive), from 'Sources:' to end or until two line breaks
        pattern = re.compile(r"\n\s*\*{0,2}Sources:\*{0,2}[\s\S]*$", re.IGNORECASE)
        cleaned = re.sub(pattern, "", answer).rstrip()

        source_list = "\n".join([f"- {name}" for name in sorted(source_files)])
        return f"{cleaned}\n\n**Sources:**\n{source_list}"

    def answer(self, query: str, top_k: int = 5, collection_id: str = None, allowed_file_ids: Optional[set] = None) -> str:
        """Main pipeline: retrieve → medium-detailed answer with source references using collection-specific prompt."""
        if self._is_small_talk(query):
            return self._handle_small_talk(query)

        chunks_with_sources = self.retrieve_chunks(query, top_k=top_k, collection_id=collection_id, allowed_file_ids=allowed_file_ids)
        if not chunks_with_sources:
            return "I wasn't able to retrieve a confident answer, please refine your question."

        system_prompt, model, max_tokens, temperature = self._resolve_prompt_settings(collection_id)

        # Build context with source information
        context_parts = []
        source_files = set()
        
        for i, chunk in enumerate(chunks_with_sources):
            context_parts.append(f"Source {i+1} (from {chunk['file_name']}):\n{chunk['text']}")
            source_files.add(chunk['file_name'])
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Enhanced prompt with source instruction
        enhanced_prompt = f"""{system_prompt}

IMPORTANT: At the end of your response, always include a "Sources:" section listing the specific files you referenced.

Context from uploaded documents:
{context}

Question: {query}
Answer:"""
        
        answer = self.call_ai(enhanced_prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        return self._inject_sources(answer, source_files)

    def answer_with_context(
        self,
        query: str,
        conversation_history: List,
        top_k: int = 5,
        collection_id: Optional[str] = None,
        allowed_file_ids: Optional[set] = None
    ) -> str:
        """Main pipeline with conversation context: retrieve → contextual answer with source references."""
        if self._is_small_talk(query):
            return self._handle_small_talk(query)

        chunks_with_sources = self.retrieve_chunks(query, top_k=top_k, collection_id=collection_id, allowed_file_ids=allowed_file_ids)
        if not chunks_with_sources:
            return "I wasn't able to retrieve a confident answer, please refine your question."

        system_prompt, model, max_tokens, temperature = self._resolve_prompt_settings(collection_id)

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

        # Build context with source information
        context_parts = []
        source_files = set()
        
        for i, chunk in enumerate(chunks_with_sources):
            context_parts.append(f"Source {i+1} (from {chunk['file_name']}):\n{chunk['text']}")
            source_files.add(chunk['file_name'])
        
        context = "\n\n---\n\n".join(context_parts)
        
        prompt_header = system_prompt
        if conversation_context:
            prompt_header = f"{system_prompt}{conversation_context}"

        enhanced_prompt = f"""{prompt_header}

IMPORTANT: At the end of your response, always include a "Sources:" section listing the specific files you referenced.

Context from uploaded documents:
{context}

Question: {query}
Answer:"""
        
        answer = self.call_ai(enhanced_prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        return self._inject_sources(answer, source_files)
