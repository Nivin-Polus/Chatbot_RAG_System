from typing import List, Dict, Optional, Tuple, Union
import requests
import json
import re

try:
    import boto3
except ImportError:
    boto3 = None
from sqlalchemy.orm import Session
from app.config import settings
from app.models.system_prompt import SystemPrompt
from app.models.collection import Collection
from app.core.database import get_db

# AI Classification instruction - appended to every prompt independently of user-configurable system prompts
# This ensures users cannot disable the generic detection functionality
CLASSIFICATION_INSTRUCTION = """

[SYSTEM CLASSIFICATION INSTRUCTION - DO NOT OMIT]
After your response, you MUST add one of these tags on a new line:
- If you were able to provide a helpful, substantive answer based on the provided context: [RESPONSE_TYPE:INFORMATIVE]
- If you could NOT find relevant information in the context, OR the question is just a greeting/small talk, OR you had to say "I don't have information": [RESPONSE_TYPE:GENERIC]

This tag is required for internal processing. Place it at the very end of your response.
"""

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
    def __init__(self, db_session=None):
        self.db_session = db_session
        self._vector_store = None

        # LLM configuration
        self.ai_provider = getattr(settings, "AI_PROVIDER", "claude").lower()
        self.api_key = getattr(settings, "CLAUDE_API_KEY", None)
        self.endpoint = getattr(settings, "CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
        self.default_model = getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307")
        self.default_max_tokens = getattr(settings, "CLAUDE_MAX_TOKENS", 4000)
        self.default_temperature = getattr(settings, "CLAUDE_TEMPERATURE", 0.7)
        self.default_system_prompt = getattr(settings, "SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

        # AWS Bedrock setup (lazy init)
        self.aws_region = getattr(settings, "AWS_REGION", "us-east-1")
        self.aws_model = getattr(settings, "AWS_MODEL", "anthropic.claude-3-5-sonnet-20241022-v1:0")
        self._bedrock_client = None

    def _get_bedrock_client(self):
        """Lazily initialize AWS Bedrock client."""
        if not self._bedrock_client:
            if boto3 is None:
                raise ImportError("boto3 is required for AWS Bedrock support but is not installed")
            # Check if AWS credentials are available in settings
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.aws_region,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
            else:
                # Use default credentials (from IAM roles, ~/.aws/credentials, etc.)
                self._bedrock_client = boto3.client("bedrock-runtime", region_name=self.aws_region)
        return self._bedrock_client
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

    def _handle_small_talk(self, query: str) -> Dict[str, any]:
        """Return a friendly response for small talk interactions."""
        return {
            "answer": "Hello! I'm here to help with questions about your knowledge base documents. "
                      "Let me know what you'd like to learn or explore.",
            "is_generic": True
        }

    def _parse_ai_response(self, raw_response: str) -> Dict[str, any]:
        """Parse AI response to extract the classification tag and clean answer.
        
        Returns:
            dict with 'answer' (cleaned text) and 'is_generic' (bool)
        """
        if not raw_response:
            return {"answer": "", "is_generic": True}
        
        # Look for the classification tag anywhere in the response (typically at the end)
        # Pattern matches the tag with optional surrounding whitespace/newlines
        informative_pattern = r'\s*\[RESPONSE_TYPE:INFORMATIVE\]\s*'
        generic_pattern = r'\s*\[RESPONSE_TYPE:GENERIC\]\s*'
        
        is_generic = False
        cleaned_response = raw_response
        
        # Check for informative tag
        if re.search(r'\[RESPONSE_TYPE:INFORMATIVE\]', raw_response, re.IGNORECASE):
            is_generic = False
            cleaned_response = re.sub(informative_pattern, '', raw_response, flags=re.IGNORECASE).strip()
        # Check for generic tag
        elif re.search(r'\[RESPONSE_TYPE:GENERIC\]', raw_response, re.IGNORECASE):
            is_generic = True
            cleaned_response = re.sub(generic_pattern, '', raw_response, flags=re.IGNORECASE).strip()
        else:
            # Fallback: If no tag found, use heuristic based on common "I don't know" phrases
            # This is a safety net in case the AI doesn't follow instructions
            fallback_generic_patterns = [
                r"i don't have (any |enough )?information",
                r"i do not have (any |enough )?information",
                r"i wasn't able to (find|retrieve)",
                r"i couldn't find",
                r"no relevant information",
                r"please refine your question",
                r"not covered in the knowledge base",
                r"unfortunately.{0,50}(don't|do not|cannot|can't|unable|no information)",
                r"i apologize.{0,30}(don't|do not|cannot|can't|unable)",
                r"outside of my scope",
                r"i'm (not able|unable) to",
                r"i am (not able|unable) to",
                r"beyond my (knowledge|scope|capabilities)",
                r"i'm here to help with questions about your knowledge base",
                r"let me know what you'd like to learn",
            ]
            normalized = raw_response.lower()
            for pattern in fallback_generic_patterns:
                if re.search(pattern, normalized):
                    is_generic = True
                    break
        
        return {"answer": cleaned_response, "is_generic": is_generic}

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
            logging.error(f"Error getting prompt for collection {collection_id}: {e}")
            return None

    def retrieve_chunks(self, query: str, top_k: int = 5, collection_id: Optional[str] = None) -> List[Dict]:
        """Search vector DB and return top matching chunks with metadata."""
        # Handle None collection_id properly
        collection_id_str = collection_id if collection_id is not None else None
        results = self.vector_store.search(query, top_k=top_k, collection_id=collection_id_str)
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
            chunks_with_sources.append({
                "text": payload.get("text", ""),
                "file_name": payload.get("file_name", "Unknown File"),
                "file_id": payload.get("file_id", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "source_type": payload.get("source_type", "file"),
                "url": payload.get("url", ""),
                "canonical_url": payload.get("canonical_url", "")
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
                logging.error(f"Error updating prompt usage: {e}")

        return system_prompt, model, max_tokens, temperature

    def call_ai(self, prompt: str, model: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        """Call the configured AI provider (Anthropic or Bedrock)."""
        model = model or self.default_model
        max_tokens = max_tokens or self.default_max_tokens
        temperature = temperature or self.default_temperature

        try:
            # --- Case 1: Anthropic direct API ---
            if self.ai_provider == "claude":
                response = requests.post(
                    self.endpoint,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=20
                )
                response.raise_for_status()
                data = response.json()
                return data.get("content", [{}])[0].get("text", "").strip()

            # --- Case 2: AWS Bedrock ---
            elif self.ai_provider == "bedrock":
                client = self._get_bedrock_client()
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}]
                })
                response = client.invoke_model(
                    modelId=self.aws_model,
                    body=body
                )
                data = json.loads(response["body"].read())
                return data["content"][0]["text"].strip()

            else:
                raise ValueError(f"Unsupported AI_PROVIDER: {self.ai_provider}")

        except Exception as e:
            logging.error(f"AI Provider Error ({self.ai_provider}): {e}")
            return "I wasn't able to retrieve a confident answer, please refine your question."

    def answer(self, query: str, top_k: int = 5, collection_id: Optional[str] = None) -> Union[str, Dict[str, any]]:
        """Main pipeline: retrieve → medium-detailed answer with source references using collection-specific prompt.
        
        Returns:
            dict with 'answer' (str) and 'is_generic' (bool) for AI classification
        """
        if self._is_small_talk(query):
            return self._handle_small_talk(query)

        chunks_with_sources = self.retrieve_chunks(query, top_k=top_k, collection_id=collection_id)
        if not chunks_with_sources:
            return {
                "answer": "I wasn't able to retrieve a confident answer, please refine your question.",
                "is_generic": True
            }

        system_prompt, model, max_tokens, temperature = self._resolve_prompt_settings(collection_id)

        # Build context with source information
        context_parts = []
        source_files = {}  # Dict to store source metadata (file_id, source_type, url)
        
        for i, chunk in enumerate(chunks_with_sources):
            context_parts.append(f"Source {i+1} (from {chunk['file_name']}):\n{chunk['text']}")
            # Store source metadata for frontend rendering
            if chunk['file_name'] not in source_files:
                source_files[chunk['file_name']] = {
                    'file_id': chunk.get('file_id', ''),
                    'source_type': chunk.get('source_type', 'file'),
                    'url': chunk.get('url', '') or chunk.get('canonical_url', '')
                }
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Enhanced prompt with source instruction + classification instruction (tamper-proof)
        enhanced_prompt = f"""{system_prompt}

IMPORTANT: At the end of your response, always include a "Sources:" section listing the specific files you referenced.

Context from uploaded documents:
{context}

Question: {query}
Answer:"""
        # Append classification instruction (cannot be overridden by user-configurable prompts)
        enhanced_prompt += CLASSIFICATION_INSTRUCTION
        
        # Extract values from SQLAlchemy model objects
        model_value = model if isinstance(model, str) else getattr(model, 'model_name', self.default_model)
        max_tokens_value = max_tokens if isinstance(max_tokens, int) else getattr(max_tokens, 'max_tokens', self.default_max_tokens)
        temperature_value = temperature if isinstance(temperature, (int, float)) else getattr(temperature, 'temperature', self.default_temperature)
        
        raw_answer = self.call_ai(enhanced_prompt, model=model_value, max_tokens=max_tokens_value, temperature=temperature_value)
        
        # Parse AI response to extract classification
        parsed = self._parse_ai_response(raw_answer)
        answer = parsed["answer"]
        is_generic = parsed["is_generic"]
        
        # ALWAYS add formatted sources - remove any AI-generated sources section first
        # Format: [file_name](reference|source_type) for frontend parsing
        # reference = file_id for files, url for web_crawl
        # Remove any existing sources section (case-insensitive)
        answer = re.sub(r'\n+\**\s*[Ss]ources?:?\s*\**[\s\S]*$', '', answer).strip()
        
        # Build and append formatted sources
        source_list = []
        for file_name, info in sorted(source_files.items()):
            source_type = info.get('source_type', 'file')
            if source_type == 'web_crawl' and info.get('url'):
                reference = info['url']
            else:
                reference = info.get('file_id', '')
            source_list.append(f"- [{file_name}]({reference}|{source_type})")
        
        if source_list:
            answer += f"\n\n**Sources:**\n" + "\n".join(source_list)

        return {"answer": answer, "is_generic": is_generic}

    def answer_with_context(
        self,
        query: str,
        conversation_history: List,
        top_k: int = 5,
        collection_id: Optional[str] = None
    ) -> Union[str, Dict[str, any]]:
        """Main pipeline with conversation context: retrieve → contextual answer with source references.
        
        Returns:
            dict with 'answer' (str) and 'is_generic' (bool) for AI classification
        """
        if self._is_small_talk(query):
            return self._handle_small_talk(query)

        chunks_with_sources = self.retrieve_chunks(query, top_k=top_k, collection_id=collection_id)
        if not chunks_with_sources:
            return {
                "answer": "I wasn't able to retrieve a confident answer, please refine your question.",
                "is_generic": True
            }

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
        source_files = {}  # Dict to store source metadata (file_id, source_type, url)
        
        for i, chunk in enumerate(chunks_with_sources):
            context_parts.append(f"Source {i+1} (from {chunk['file_name']}):\n{chunk['text']}")
            # Store source metadata for frontend rendering
            if chunk['file_name'] not in source_files:
                source_files[chunk['file_name']] = {
                    'file_id': chunk.get('file_id', ''),
                    'source_type': chunk.get('source_type', 'file'),
                    'url': chunk.get('url', '') or chunk.get('canonical_url', '')
                }
        
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
        # Append classification instruction (cannot be overridden by user-configurable prompts)
        enhanced_prompt += CLASSIFICATION_INSTRUCTION
        
        # Extract values from SQLAlchemy model objects
        model_value = model if isinstance(model, str) else getattr(model, 'model_name', self.default_model)
        max_tokens_value = max_tokens if isinstance(max_tokens, int) else getattr(max_tokens, 'max_tokens', self.default_max_tokens)
        temperature_value = temperature if isinstance(temperature, (int, float)) else getattr(temperature, 'temperature', self.default_temperature)
        
        raw_answer = self.call_ai(enhanced_prompt, model=model_value, max_tokens=max_tokens_value, temperature=temperature_value)
        
        # Parse AI response to extract classification
        parsed = self._parse_ai_response(raw_answer)
        answer = parsed["answer"]
        is_generic = parsed["is_generic"]
        
        # ALWAYS add formatted sources - remove any AI-generated sources section first
        # Format: [file_name](reference|source_type) for frontend parsing
        # reference = file_id for files, url for web_crawl
        # Remove any existing sources section (case-insensitive)
        answer = re.sub(r'\n+\**\s*[Ss]ources?:?\s*\**[\s\S]*$', '', answer).strip()
        
        # Build and append formatted sources
        source_list = []
        for file_name, info in sorted(source_files.items()):
            source_type = info.get('source_type', 'file')
            if source_type == 'web_crawl' and info.get('url'):
                reference = info['url']
            else:
                reference = info.get('file_id', '')
            source_list.append(f"- [{file_name}]({reference}|{source_type})")
        
        if source_list:
            answer += f"\n\n**Sources:**\n" + "\n".join(source_list)

        return {"answer": answer, "is_generic": is_generic}
