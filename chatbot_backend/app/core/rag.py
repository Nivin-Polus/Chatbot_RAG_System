from typing import List, Dict, Optional, Tuple, Union, Set
import requests
import json
import re
import logging

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
from sqlalchemy.orm import Session
from app.config import settings
from app.models.system_prompt import SystemPrompt
from app.models.collection import Collection
from app.core.database import get_db

# Initialize logger
logger = logging.getLogger("rag")
logging.basicConfig(level=logging.INFO)

# RAG limits to prevent overloading LLM context
MAX_QUERY_EXPANSIONS = 8   # Maximum queries (original + expansions)
MAX_CONTEXT_TOKENS = 2500  # Token cap for Claude Sonnet
MIN_SCORE = 0.35           # Minimum similarity threshold to filter low-confidence chunks

# Conversation summarization settings
MAX_VERBATIM_MESSAGES = 20   # Keep last 10 Q&A pairs (20 messages) verbatim
SUMMARY_TRIGGER_THRESHOLD = 20  # Start summarizing when history exceeds this count


def _estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars per token for English)."""
    return len(text) // 4 if text else 0


# ============================================
# HYBRID SEARCH HELPER FUNCTIONS
# ============================================

# Hybrid scoring weights
VECTOR_WEIGHT = 0.50
KEYWORD_WEIGHT = 0.35
FUZZY_WEIGHT = 0.15

# Fuzzy search constraints
FUZZY_SCORE_CAP = 0.55  # Hard cap on fuzzy contribution
FUZZY_MAX_TEXT_LENGTH = 300  # Only apply fuzzy to short chunks

# Field weights for keyword scoring
KEYWORD_FIELD_WEIGHTS = {
    "page_title": 1.0,      # chunk_title equivalent for web crawl
    "section_header": 0.8,  # section_title equivalent for web crawl
    "file_name": 0.6,
    "first_sentence": 0.5,
}


def _tokenize(text: str) -> Set[str]:
    """Lowercase tokenization with basic normalization.
    
    Removes punctuation and splits on whitespace.
    Returns empty set for None/empty input.
    """
    if not text:
        return set()
    # Remove punctuation and normalize
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    # Split and filter empty strings
    return {token for token in normalized.split() if token and len(token) > 1}


def _get_first_sentence(text: str) -> str:
    """Extract first sentence from chunk text for keyword matching."""
    if not text:
        return ""
    # Find first sentence ending
    match = re.search(r'^[^.!?\n]+[.!?]?', text.strip())
    return match.group(0) if match else text[:150]


def _compute_keyword_score(query_tokens: Set[str], payload: Dict, chunk_text: str) -> float:
    """Compute weighted Jaccard similarity across target fields.
    
    Target fields (with weights):
    - page_title (1.0) - for web crawl chunks
    - section_header (0.8) - for web crawl chunks
    - file_name (0.6) - for all chunks
    - first_sentence (0.5) - first sentence of chunk_text
    
    Returns normalized score in [0.0, 1.0].
    """
    if not query_tokens:
        return 0.0
    
    total_weighted_score = 0.0
    total_weight = 0.0
    
    # page_title (for web crawl)
    page_title = payload.get("page_title", "")
    if page_title:
        field_tokens = _tokenize(page_title)
        if field_tokens:
            overlap = len(query_tokens & field_tokens)
            union = len(query_tokens | field_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            total_weighted_score += jaccard * KEYWORD_FIELD_WEIGHTS["page_title"]
            total_weight += KEYWORD_FIELD_WEIGHTS["page_title"]
    
    # section_header (for web crawl)
    section_header = payload.get("section_header", "")
    if section_header:
        field_tokens = _tokenize(section_header)
        if field_tokens:
            overlap = len(query_tokens & field_tokens)
            union = len(query_tokens | field_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            total_weighted_score += jaccard * KEYWORD_FIELD_WEIGHTS["section_header"]
            total_weight += KEYWORD_FIELD_WEIGHTS["section_header"]
    
    # file_name (for all chunks)
    file_name = payload.get("file_name", "")
    if file_name:
        # Clean file extensions for matching
        clean_name = re.sub(r'\.(pdf|docx|pptx|xlsx|txt|csv|html?)$', '', file_name, flags=re.IGNORECASE)
        field_tokens = _tokenize(clean_name)
        if field_tokens:
            overlap = len(query_tokens & field_tokens)
            union = len(query_tokens | field_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            total_weighted_score += jaccard * KEYWORD_FIELD_WEIGHTS["file_name"]
            total_weight += KEYWORD_FIELD_WEIGHTS["file_name"]
    
    # first_sentence of chunk_text
    first_sentence = _get_first_sentence(chunk_text)
    if first_sentence:
        field_tokens = _tokenize(first_sentence)
        if field_tokens:
            overlap = len(query_tokens & field_tokens)
            union = len(query_tokens | field_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            total_weighted_score += jaccard * KEYWORD_FIELD_WEIGHTS["first_sentence"]
            total_weight += KEYWORD_FIELD_WEIGHTS["first_sentence"]
    
    # Normalize by total weight to get score in [0, 1]
    if total_weight > 0:
        return total_weighted_score / total_weight
    return 0.0


def _is_structured_content(text: str) -> bool:
    """Detect structured content that should skip fuzzy matching.
    
    Detects:
    - Tables (| or tab characters in patterns)
    - Code blocks (triple backticks)
    - Log lines (timestamp patterns)
    """
    if not text:
        return False
    
    # Code blocks
    if '```' in text:
        return True
    
    # Tables (multiple | characters suggesting table structure)
    if text.count('|') >= 3:
        return True
    
    # Tab-separated data (likely table)
    if text.count('\t') >= 2:
        return True
    
    # Log line patterns (timestamp at start)
    log_pattern = r'^\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}'
    if re.search(log_pattern, text[:50]):
        return True
    
    return False


def _compute_fuzzy_score(query: str, payload: Dict, chunk_text: str) -> float:
    """Compute fuzzy matching score with safety controls.
    
    Only applies fuzzy to:
    - page_title
    - section_header
    - chunk_text IF len < 300 chars AND not structured content
    
    Returns score in [0.0, FUZZY_SCORE_CAP] (hard capped at 0.55).
    """
    if not RAPIDFUZZ_AVAILABLE:
        return 0.0
    
    if not query:
        return 0.0
    
    max_fuzzy = 0.0
    
    # Fuzzy on page_title
    page_title = payload.get("page_title", "")
    if page_title:
        ratio = fuzz.partial_ratio(query.lower(), page_title.lower())
        max_fuzzy = max(max_fuzzy, ratio / 100.0)
    
    # Fuzzy on section_header
    section_header = payload.get("section_header", "")
    if section_header:
        ratio = fuzz.partial_ratio(query.lower(), section_header.lower())
        max_fuzzy = max(max_fuzzy, ratio / 100.0)
    
    # Fuzzy on chunk_text (only if short and not structured)
    if chunk_text and len(chunk_text) < FUZZY_MAX_TEXT_LENGTH:
        if not _is_structured_content(chunk_text):
            ratio = fuzz.partial_ratio(query.lower(), chunk_text.lower())
            max_fuzzy = max(max_fuzzy, ratio / 100.0)
    
    # Apply hard cap
    return min(max_fuzzy, FUZZY_SCORE_CAP)


def _should_use_fuzzy(query: str, vector_results: List[Dict]) -> bool:
    """Determine if fuzzy scoring should be activated.
    
    Fuzzy is enabled when ANY of these conditions are true:
    - Query has 8 or fewer words
    - No vector results returned
    - Top vector score is below 0.55
    """
    # Short queries benefit from fuzzy
    if len(query.split()) <= 8:
        return True
    
    # No results - fuzzy might help
    if not vector_results:
        return True
    
    # Low confidence results - fuzzy might help
    top_score = max((r.get("score", 0) for r in vector_results), default=0)
    if top_score < 0.55:
        return True
    
    return False


def _compute_hybrid_score(
    vector_score: float,
    keyword_score: float,
    fuzzy_score: float
) -> float:
    """Apply the hybrid fusion formula.
    
    Formula: 0.50 * vector + 0.35 * keyword + 0.15 * fuzzy
    """
    return (
        VECTOR_WEIGHT * vector_score +
        KEYWORD_WEIGHT * keyword_score +
        FUZZY_WEIGHT * fuzzy_score
    )


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
                r"i encountered an error while processing",
                r"ai model is currently unavailable",
                r"ai service is temporarily overloaded",
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
        """Search vector DB and return top matching chunks with metadata.
        
        Includes query expansion for 'who is X' or title-based queries.
        Applies keyword-based score boosting for both names and job titles.
        """
        # Handle None collection_id properly
        collection_id_str = collection_id if collection_id is not None else None
        
        # Detect search subjects (names or titles)
        search_term = None
        
        # 1. Check for "who is X" patterns
        who_is_pattern = re.match(r"(?:who\s+is|who's|tell\s+me\s+about|information\s+(?:on|about))\s+(.+)", query.lower().strip())
        if who_is_pattern:
            search_term = who_is_pattern.group(1).strip().rstrip("?.,!")
        # 2. If no prefix, but query is short, treat it as a potential name/title
        elif len(query.split()) <= 4:
            # Clean common filler words
            search_term = re.sub(r"^(?:find|search|get|show|for|a)\s+", "", query.lower().strip())
        
        # Query expansion (limited to MAX_QUERY_EXPANSIONS)
        expanded_queries = [query]  # Always include original query
        
        if search_term:
            logger.info(f"[RAG QUERY EXPANSION] Detected search term: '{search_term}'")
            
            # Limited expansion queries to prevent overload
            expansion_candidates = [
                search_term,
                f"{search_term} staff directory contacts",
            ]
            # Take at most (MAX_QUERY_EXPANSIONS - 1) expansions
            expanded_queries.extend(expansion_candidates[:MAX_QUERY_EXPANSIONS - 1])
            logger.info(f"[RAG QUERY EXPANSION] Total queries: {len(expanded_queries)} (max: {MAX_QUERY_EXPANSIONS})")
        
        # Collect results from all expanded queries
        all_results = []
        seen_texts = set()  # For deduplication
        
        for i, exp_query in enumerate(expanded_queries):
            # Fetch more results to allow for boosting (especially for specific names/titles)
            search_limit = max(50, top_k * 5)
            results = self.vector_store.search(exp_query, top_k=search_limit, collection_id=collection_id_str)
            
            if i == 0:
                logger.info(f"[RAG RETRIEVE] Original query returned {len(results)} results")
            else:
                logger.debug(f"[RAG RETRIEVE] Expanded query '{exp_query}' returned {len(results)} results")
            
            for r in results:
                payload = r.get("payload", {})
                text = payload.get("text", "")
                
                # Deduplicate by text content
                text_hash = hash(text[:200]) if text else hash("")
                if text_hash in seen_texts:
                    continue
                seen_texts.add(text_hash)
                
                # Store original vector score for hybrid fusion
                vector_score = r.get("score", 0)
                r["vector_score"] = vector_score
                r["original_score"] = vector_score
                all_results.append(r)
        
        logger.info(f"[RAG RETRIEVE] Total unique results: {len(all_results)}")
        
        # ============================================
        # [HYBRID SEARCH: COMPUTE KEYWORD + FUZZY SCORES]
        # ============================================
        
        # Tokenize query once for keyword scoring
        query_tokens = _tokenize(query)
        
        # Determine if fuzzy scoring should be activated
        use_fuzzy = _should_use_fuzzy(query, all_results)
        logger.info(f"[HYBRID SEARCH] Fuzzy scoring enabled: {use_fuzzy}")
        
        # Compute hybrid scores for each result
        for r in all_results:
            payload = r.get("payload", {})
            text = payload.get("text", "")
            vector_score = r.get("vector_score", r.get("score", 0))
            
            # Compute keyword score
            keyword_score = _compute_keyword_score(query_tokens, payload, text)
            
            # Compute fuzzy score (only if activated)
            fuzzy_score = 0.0
            if use_fuzzy:
                fuzzy_score = _compute_fuzzy_score(query, payload, text)
            
            # Apply hybrid fusion formula
            final_score = _compute_hybrid_score(vector_score, keyword_score, fuzzy_score)
            
            # Apply legacy boosting for "who is X" queries (additive to hybrid)
            # This preserves backward compatibility for name/title searches
            if search_term:
                text_lower = text.lower()
                search_parts = search_term.split()
                excluded_words = ["staff", "directory", "contact", "the", "and", "for", "with", "from", "about"]
                meaningful_parts = [p for p in search_parts if len(p) > 2 and p not in excluded_words]
                
                # Exact sequence match gets highest priority
                if search_term in text_lower:
                    final_score = max(final_score, 0.85)
                elif meaningful_parts:
                    matches = [p for p in meaningful_parts if p in text_lower]
                    match_ratio = len(matches) / len(meaningful_parts) if meaningful_parts else 0
                    
                    if match_ratio >= 1.0:
                        final_score = max(final_score, 0.80)
                    elif match_ratio >= 0.75:
                        final_score = max(final_score, 0.75)
                    elif match_ratio >= 0.5:
                        final_score = max(final_score, 0.65)
                    elif matches:
                        final_score = max(final_score, 0.60)
            
            # Store scores for metadata
            r["score"] = final_score
            r["keyword_score"] = keyword_score
            r["fuzzy_score"] = fuzzy_score
            r["fusion_method"] = "hybrid" if (keyword_score > 0 or fuzzy_score > 0) else "vector_only"
        
        # Log hybrid scoring summary
        if all_results:
            top_result = max(all_results, key=lambda x: x.get("score", 0))
            logger.info(f"[HYBRID SEARCH] Top result: final={top_result.get('score', 0):.4f}, "
                       f"vector={top_result.get('vector_score', 0):.4f}, "
                       f"keyword={top_result.get('keyword_score', 0):.4f}, "
                       f"fuzzy={top_result.get('fuzzy_score', 0):.4f}")
        
        # ============================================
        # [END HYBRID SEARCH]
        # ============================================
        
        # Filter by minimum similarity score (after hybrid fusion, before sorting)
        pre_filter_count = len(all_results)
        all_results = [r for r in all_results if r.get("score", 0) >= MIN_SCORE]
        filtered_by_score = pre_filter_count - len(all_results)
        if filtered_by_score > 0:
            logger.info(f"[RAG RETRIEVE] Filtered {filtered_by_score} chunks below MIN_SCORE={MIN_SCORE}")
        
        # Filter by collection_id BEFORE sort and top_k (Bug Fix #2)
        if collection_id is not None:
            filtered_results = []
            filtered_count = 0
            for r in all_results:
                payload = r.get("payload", {})
                payload_collection_id = payload.get("collection_id")
                if payload_collection_id is None or str(payload_collection_id) != str(collection_id):
                    filtered_count += 1
                    continue
                filtered_results.append(r)
            all_results = filtered_results
            if filtered_count > 0:
                logger.info(f"[RAG RETRIEVE] Filtered {filtered_count} chunks due to collection_id mismatch")
        
        # GLOBAL sort by boosted scores
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        # HARD top_k limit - no exceptions (Bug Fix #2)
        results = all_results[:top_k]
        logger.info(f"[RAG RETRIEVE] Final result count after hard top_k={top_k}: {len(results)}")
        
        chunks_with_sources = []
        for r in results:
            payload = r.get("payload", {})
            score = r.get("score", 0)
            
            chunks_with_sources.append({
                "text": payload.get("text", ""),
                "file_name": payload.get("file_name", "Unknown File"),
                "file_id": payload.get("file_id", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "source_type": payload.get("source_type", "file"),
                "url": payload.get("url", ""),
                "canonical_url": payload.get("canonical_url", ""),
                "score": score,
                # Hybrid search metadata for debugging
                "metadata": {
                    "vector_score": r.get("vector_score", score),
                    "keyword_score": r.get("keyword_score", 0.0),
                    "fuzzy_score": r.get("fuzzy_score", 0.0),
                    "fusion_method": r.get("fusion_method", "vector_only")
                }
            })
        
        return chunks_with_sources

    # ------------------------------------------------------------------
    # Follow-up Question Detection and Generation
    # ------------------------------------------------------------------
    
    def needs_followup(self, question: str, chunks: list, threshold: float = 0.35) -> Tuple[bool, str]:
        """
        Determine if a follow-up question should be asked instead of answering.
        
        Detection criteria:
        - No relevant chunks found (len(chunks) == 0)
        - Low relevance score (top chunk score < threshold)
        - Ambiguous phrasing (e.g., "tell me more", "explain this")
        - Vague pronouns without context (e.g., "it", "this", "that")
        - Missing domain-specific context
        
        Returns:
            tuple: (needs_followup: bool, reason: str)
            Reasons: "no_relevant_chunks", "low_relevance_score", "ambiguous_phrasing", 
                     "vague_pronoun", "missing_context", "confident"
        """
        if not question:
            return True, "empty_question"
        
        normalized = question.strip().lower()
        
        # 1. Check for no relevant chunks
        if not chunks or len(chunks) == 0:
            logger.info(f"[FOLLOWUP] Triggered: no_relevant_chunks for query: {question[:50]}")
            return True, "no_relevant_chunks"
        
        # 2. Check for low relevance score
        top_score = chunks[0].get("score", 0) if chunks else 0
        if top_score < threshold:
            logger.info(f"[FOLLOWUP] Triggered: low_relevance_score ({top_score:.4f} < {threshold}) for query: {question[:50]}")
            return True, "low_relevance_score"
        
        # 3. Check for ambiguous phrasing
        ambiguous_phrases = [
            "tell me more",
            "explain this",
            "what about",
            "can you elaborate",
            "more details",
            "more information",
            "explain that",
            "tell me about it",
            "what does it mean",
            "how does it work",
            "why is that",
            "what is it",
            "what are they",
            "what about this",
            "what about that",
        ]
        for phrase in ambiguous_phrases:
            if phrase in normalized:
                logger.info(f"[FOLLOWUP] Triggered: ambiguous_phrasing ('{phrase}') for query: {question[:50]}")
                return True, "ambiguous_phrasing"
        
        # 4. Check for vague pronouns without sufficient context
        # Short queries with only pronouns are likely ambiguous
        vague_patterns = [
            r"^(?:what|how|why|when|where)\s+(?:is|are|was|were|does|do|did)\s+(?:it|this|that|these|those)\??$",
            r"^(?:explain|describe|tell me about)\s+(?:it|this|that|these|those)\??$",
            r"^(?:it|this|that)\s+(?:is|was|does|did|has|have)\s+\w+\??$",
        ]
        for pattern in vague_patterns:
            if re.match(pattern, normalized):
                logger.info(f"[FOLLOWUP] Triggered: vague_pronoun for query: {question[:50]}")
                return True, "vague_pronoun"
        
        # 5. Check for missing critical domain context
        if self._missing_critical_context(question):
            logger.info(f"[FOLLOWUP] Triggered: missing_context for query: {question[:50]}")
            return True, "missing_context"
        
        # All checks passed - confident to answer
        return False, "confident"

    def _missing_critical_context(self, question: str) -> bool:
        """
        Check for domain-specific missing information.
        
        This method can be customized based on the knowledge base domain.
        Examples:
        - Agriculture: mentions "fertilizer" but no crop type
        - Product support: mentions "install" but no version
        - Legal: mentions "law" but no jurisdiction
        
        Returns:
            bool: True if critical context is missing
        """
        normalized = question.lower()
        
        # Example domain rules (customize based on your knowledge base)
        domain_rules = [
            # Agriculture domain
            {
                "trigger_keywords": ["fertilizer", "pesticide", "irrigation", "planting"],
                "required_context": ["crop", "plant", "rice", "wheat", "corn", "vegetable", "fruit"],
                "description": "agricultural query without crop type"
            },
            # Product support domain
            {
                "trigger_keywords": ["install", "upgrade", "update", "download"],
                "required_context": ["version", "v1", "v2", "windows", "mac", "linux", "android", "ios"],
                "description": "installation query without platform/version"
            },
        ]
        
        for rule in domain_rules:
            # Check if any trigger keyword is present
            has_trigger = any(kw in normalized for kw in rule["trigger_keywords"])
            if has_trigger:
                # Check if any required context is present
                has_context = any(ctx in normalized for ctx in rule["required_context"])
                if not has_context:
                    logger.debug(f"[FOLLOWUP] Missing context: {rule['description']}")
                    return True
        
        return False

    def generate_followup_questions(self, question: str, chunks: list, reason: str) -> str:
        """
        Generate 1-2 specific clarifying questions using the AI model.
        
        Rules for generation:
        - Keep questions short and specific
        - Provide multiple-choice options when possible
        - Do NOT attempt to answer the original question
        - Be friendly and helpful in tone
        
        If AI call fails, fall back to generic questions based on reason.
        
        Returns:
            str: The generated follow-up question(s)
        """
        # Build context from available chunks (if any)
        chunk_context = ""
        if chunks and len(chunks) > 0:
            # Use top 3 chunks for context about available topics
            top_chunks = chunks[:3]
            topics = set()
            for chunk in top_chunks:
                text = chunk.get("text", "")[:200]
                file_name = chunk.get("file_name", "")
                if file_name:
                    topics.add(file_name.replace(".pdf", "").replace(".docx", "").replace("_", " "))
            if topics:
                chunk_context = f"Available topics in the knowledge base include: {', '.join(list(topics)[:5])}"
        
        # Reason-specific prompt hints
        reason_hints = {
            "no_relevant_chunks": "The user's question doesn't match any content in our knowledge base.",
            "low_relevance_score": "The user's question has low relevance to available content.",
            "ambiguous_phrasing": "The user's question is vague and needs clarification.",
            "vague_pronoun": "The user used pronouns (it, this, that) without clear context.",
            "missing_context": "The user's question is missing important context (e.g., specific category, version, or type).",
        }
        
        hint = reason_hints.get(reason, "The user's question needs clarification.")
        
        prompt = f"""You are a helpful assistant. A user asked a question that needs clarification before you can provide a good answer.

User's question: "{question}"

Situation: {hint}
{chunk_context}

Your task: Generate 1-2 SHORT, SPECIFIC clarifying questions to ask the user. 

Rules:
1. Keep each question to ONE sentence
2. Offer specific options when possible (e.g., "Are you asking about X or Y?")
3. Be friendly and helpful
4. Do NOT try to answer the original question
5. Do NOT apologize excessively

Respond with ONLY the clarifying question(s), nothing else."""

        try:
            followup_text, _ = self.call_ai(
                prompt,
                max_tokens=200,  # Keep responses concise
                temperature=0.7
            )
            
            # Clean up the response
            followup_text = followup_text.strip()
            
            # Remove any classification tags that might leak through
            followup_text = re.sub(r'\[RESPONSE_TYPE:\w+\]', '', followup_text).strip()
            
            if followup_text:
                logger.info(f"[FOLLOWUP] Generated AI follow-up: {followup_text[:100]}")
                return followup_text
            else:
                return self._get_generic_followup(reason)
                
        except Exception as e:
            logger.error(f"[FOLLOWUP] AI generation failed: {e}")
            return self._get_generic_followup(reason)

    def _get_generic_followup(self, reason: str) -> str:
        """Fallback follow-up questions when AI generation fails."""
        fallbacks = {
            "no_relevant_chunks": "I couldn't find information related to your question. Could you please provide more details about what you're looking for?",
            "low_relevance_score": "I'm not fully confident about what you're asking. Could you rephrase your question or provide more context?",
            "ambiguous_phrasing": "Your question is a bit broad. Could you be more specific about what aspect you'd like to know?",
            "vague_pronoun": "I'm not sure what you're referring to. Could you please specify what 'it' or 'this' refers to?",
            "missing_context": "I need a bit more information to help you. Could you provide additional details like the specific type, category, or version you're asking about?",
            "empty_question": "I didn't receive a question. What would you like to know?",
        }
        
        return fallbacks.get(reason, "Could you please clarify your question so I can better assist you?")

    def summarize_conversation(self, older_messages: List) -> str:
        """
        Summarize older conversation messages to preserve context without overwhelming the LLM.
        
        Called when conversation_history exceeds MAX_VERBATIM_MESSAGES.
        Uses the LLM to generate a concise summary of key points.
        
        Args:
            older_messages: List of conversation messages (dicts or Pydantic objects) to summarize
            
        Returns:
            str: A concise summary of the conversation history
        """
        if not older_messages:
            return ""
        
        # Build conversation text from older messages
        conversation_text = ""
        for msg in older_messages:
            # Handle both Pydantic objects and dictionaries
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                role = "User" if msg.role == "user" else "Assistant"
                content = msg.content
            else:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
            
            conversation_text += f"{role}: {content}\n"
        
        # Estimate tokens to avoid too long summaries
        estimated_tokens = _estimate_tokens(conversation_text)
        logger.info(f"[SUMMARIZATION] Summarizing {len(older_messages)} older messages (~{estimated_tokens} tokens)")
        
        summary_prompt = f"""You are summarizing a conversation between a user and an AI assistant for context preservation.

Conversation to summarize:
{conversation_text}

Create a CONCISE summary (max 200 words) that captures:
1. Main topics discussed
2. Key questions the user asked
3. Important information or answers provided
4. Any decisions or conclusions reached

Write the summary in third person (e.g., "The user asked about...", "The assistant explained...").
Focus on information that would be useful for continuing the conversation.

Summary:"""

        try:
            summary_text, _ = self.call_ai(
                summary_prompt,
                max_tokens=300,  # Keep summary concise
                temperature=0.3  # Lower temperature for more focused summary
            )
            
            # Clean up the response
            summary_text = summary_text.strip()
            
            # Remove any classification tags that might leak through
            summary_text = re.sub(r'\[RESPONSE_TYPE:\w+\]', '', summary_text).strip()
            
            if summary_text:
                logger.info(f"[SUMMARIZATION] Summary generated: {summary_text[:100]}...")
                return summary_text
            else:
                logger.warning("[SUMMARIZATION] Empty summary generated, using fallback")
                return self._get_fallback_summary(older_messages)
                
        except Exception as e:
            logger.error(f"[SUMMARIZATION] AI summarization failed: {e}")
            return self._get_fallback_summary(older_messages)
    
    def _get_fallback_summary(self, messages: List) -> str:
        """Generate a simple fallback summary when AI summarization fails."""
        user_messages = []
        for msg in messages:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                if msg.role == "user":
                    user_messages.append(msg.content[:50])
            elif msg.get("role") == "user":
                user_messages.append(msg.get("content", "")[:50])
        
        if user_messages:
            topics = ", ".join(user_messages[:3])
            return f"Earlier in the conversation, the user asked about: {topics}..."
        return "The conversation covered various topics earlier."

    def _resolve_prompt_settings(self, collection_id: Optional[str] = None):
        """Determine system prompt and model configuration for the given collection.
        
        Note: model, max_tokens, and temperature are ALWAYS taken from environment
        variables (self.default_*). Only the system_prompt text is taken from the
        database if a collection-specific prompt exists.
        """
        db_prompt = None
        if collection_id:
            db_prompt = self.get_prompt_for_collection(collection_id)

        if db_prompt:
            # Use prompt text from database, but model settings from env
            system_prompt = db_prompt.system_prompt
        else:
            system_prompt = self.default_system_prompt
        
        # ALWAYS use env defaults for model configuration
        model = self.default_model
        max_tokens = self.default_max_tokens
        temperature = self.default_temperature

        if db_prompt and self.db_session:
            try:
                db_prompt.increment_usage(self.db_session)
            except Exception as e:
                logger.error(f"Error updating prompt usage: {e}")

        return system_prompt, model, max_tokens, temperature

    def call_ai(self, prompt: str, model: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> Tuple[str, Optional[int]]:
        """Call the configured AI provider (Anthropic or Bedrock).

        Returns:
            A tuple of (raw_text_response, total_tokens_used or None)
        """
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
                    timeout=120
                )
                response.raise_for_status()
                data = response.json()

                # Extract text
                text = data.get("content", [{}])[0].get("text", "").strip()

                # Extract token usage if available
                usage = data.get("usage") or {}
                input_tokens = usage.get("input_tokens") or 0
                output_tokens = usage.get("output_tokens") or 0
                try:
                    tokens_used = int(input_tokens) + int(output_tokens)
                except (TypeError, ValueError):
                    tokens_used = None

                return text, tokens_used

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

                text = data.get("content", [{}])[0].get("text", "").strip()

                # Bedrock responses may or may not include usage; handle defensively
                usage = data.get("usage") or {}
                input_tokens = usage.get("input_tokens") or 0
                output_tokens = usage.get("output_tokens") or 0
                try:
                    tokens_used = int(input_tokens) + int(output_tokens)
                except (TypeError, ValueError):
                    tokens_used = None

                return text, tokens_used

            else:
                raise ValueError(f"Unsupported AI_PROVIDER: {self.ai_provider}")

        except Exception as e:
            error_str = str(e)
            logger.error(f"AI Provider Error ({self.ai_provider}): {e}")
            
            # Return consistent error message for all LLM failures (tagged as generic)
            return "I encountered an error while processing your question. Please try again. [RESPONSE_TYPE:GENERIC]", None

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

        # Build context with source information and TOKEN CAP (Bug Fix #3)
        context_parts = []
        source_files = {}  # Dict to store source metadata (file_id, source_type, url)
        total_tokens = 0
        
        for i, chunk in enumerate(chunks_with_sources):
            chunk_text = chunk['text']
            chunk_tokens = _estimate_tokens(chunk_text)
            
            # Check token cap before adding
            if total_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                logger.info(f"[RAG TOKEN CAP] Stopping at {i} chunks, {total_tokens} tokens (limit: {MAX_CONTEXT_TOKENS})")
                break
            
            total_tokens += chunk_tokens
            context_parts.append(f"Source {i+1} (from {chunk['file_name']}):\n{chunk_text}")
            # Store source metadata for frontend rendering
            if chunk['file_name'] not in source_files:
                source_files[chunk['file_name']] = {
                    'file_id': chunk.get('file_id', ''),
                    'source_type': chunk.get('source_type', 'file'),
                    'url': chunk.get('url', '') or chunk.get('canonical_url', '')
                }
        
        logger.info(f"[RAG CONTEXT] Using {len(context_parts)} chunks, ~{total_tokens} tokens")
        
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
        
        # Debug logging to trace max_tokens value
        logger.info(f"[RAG AI CALL] Using max_tokens={max_tokens_value}, model={model_value}, temperature={temperature_value}")
        
        raw_answer, tokens_used = self.call_ai(
            enhanced_prompt,
            model=model_value,
            max_tokens=max_tokens_value,
            temperature=temperature_value,
        )
        
        # Log LLM response details
        logger.info(f"[LLM RESPONSE] Provider: {self.ai_provider}, Model: {model_value}")
        logger.info(f"[LLM RESPONSE] Tokens used: {tokens_used}")
        logger.info(f"[LLM RESPONSE] Response length: {len(raw_answer)} chars")
        logger.info(f"[LLM RESPONSE] Full response:\n{raw_answer}")
        
        # Parse AI response to extract classification
        parsed = self._parse_ai_response(raw_answer)
        answer = parsed["answer"]
        is_generic = parsed["is_generic"]
        
        # Force is_generic=True if AI call failed (no tokens used or error text detected)
        if tokens_used is None or "I encountered an error while processing your question" in answer:
            is_generic = True
        
        logger.info(f"[RAG DEBUG] Parsed answer length: {len(answer)} chars")
        
        # ALWAYS add formatted sources - remove any AI-generated sources section first
        # Format: [file_name](reference|source_type) for frontend parsing
        # reference = file_id for files, url for web_crawl
        # Remove any existing sources section (case-insensitive) - handles with or without preceding newline
        answer = re.sub(r'(?:^|\n)\s*\**\s*\bSources?\b:?\s*\**\s*(?:\n[\s\S]*)?$', '', answer, flags=re.IGNORECASE).strip()
        
        logger.info(f"[RAG DEBUG] After sources strip length: {len(answer)} chars")
        
        # Build and append formatted sources ONLY if not a generic response
        if not is_generic:
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

        return {"answer": answer, "is_generic": is_generic, "tokens_used": tokens_used}

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

        # Build conversation context with summarization for long histories
        conversation_context = ""
        if conversation_history:
            history_length = len(conversation_history)
            
            # Check if we need to summarize older messages
            if history_length > SUMMARY_TRIGGER_THRESHOLD:
                # Split: older messages (to summarize) + recent messages (verbatim)
                older_messages = conversation_history[:-MAX_VERBATIM_MESSAGES]
                recent_messages = conversation_history[-MAX_VERBATIM_MESSAGES:]
                
                logger.info(f"[CONTEXT] History length {history_length} exceeds threshold {SUMMARY_TRIGGER_THRESHOLD}")
                logger.info(f"[CONTEXT] Summarizing {len(older_messages)} older messages, keeping {len(recent_messages)} verbatim")
                
                # Generate summary of older messages
                summary = self.summarize_conversation(older_messages)
                
                # Build context with summary + recent verbatim messages
                conversation_context = "\n\n[Conversation Summary (earlier messages)]:\n"
                conversation_context += f"{summary}\n"
                conversation_context += "\n[Recent Conversation (last 10 Q&A pairs)]:\n"
                
                for msg in recent_messages:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        role = "Human" if msg.role == "user" else "Assistant"
                        content = msg.content
                    else:
                        role = "Human" if msg.get("role") == "user" else "Assistant"
                        content = msg.get("content", "")
                    conversation_context += f"{role}: {content}\n"
            else:
                # History is within limit, use all messages verbatim
                conversation_context = "\n\nPrevious Conversation:\n"
                for msg in conversation_history:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        role = "Human" if msg.role == "user" else "Assistant"
                        content = msg.content
                    else:
                        role = "Human" if msg.get("role") == "user" else "Assistant"
                        content = msg.get("content", "")
                    conversation_context += f"{role}: {content}\n"

        # Build context with source information and TOKEN CAP (Bug Fix #3)
        context_parts = []
        source_files = {}  # Dict to store source metadata (file_id, source_type, url)
        total_tokens = 0
        
        for i, chunk in enumerate(chunks_with_sources):
            chunk_text = chunk['text']
            chunk_tokens = _estimate_tokens(chunk_text)
            
            # Check token cap before adding
            if total_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                logger.info(f"[RAG TOKEN CAP] Stopping at {i} chunks, {total_tokens} tokens (limit: {MAX_CONTEXT_TOKENS})")
                break
            
            total_tokens += chunk_tokens
            context_parts.append(f"Source {i+1} (from {chunk['file_name']}):\n{chunk_text}")
            # Store source metadata for frontend rendering
            if chunk['file_name'] not in source_files:
                source_files[chunk['file_name']] = {
                    'file_id': chunk.get('file_id', ''),
                    'source_type': chunk.get('source_type', 'file'),
                    'url': chunk.get('url', '') or chunk.get('canonical_url', '')
                }
        
        logger.info(f"[RAG CONTEXT] Using {len(context_parts)} chunks, ~{total_tokens} tokens")
        
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
        
        # Debug logging to trace max_tokens value
        logger.info(f"[RAG AI CALL WITH CONTEXT] Using max_tokens={max_tokens_value}, model={model_value}, temperature={temperature_value}")
        
        raw_answer, tokens_used = self.call_ai(
            enhanced_prompt,
            model=model_value,
            max_tokens=max_tokens_value,
            temperature=temperature_value,
        )
        
        # Log LLM response details
        logger.info(f"[LLM RESPONSE] Provider: {self.ai_provider}, Model: {model_value}")
        logger.info(f"[LLM RESPONSE] Tokens used: {tokens_used}")
        logger.info(f"[LLM RESPONSE] Response length: {len(raw_answer)} chars")
        logger.info(f"[LLM RESPONSE] Full response:\n{raw_answer}")
        
        # Parse AI response to extract classification
        parsed = self._parse_ai_response(raw_answer)
        answer = parsed["answer"]
        is_generic = parsed["is_generic"]
        
        # Force is_generic=True if AI call failed (no tokens used or error text detected)
        if tokens_used is None or "I encountered an error while processing your question" in answer:
            is_generic = True
        
        # ALWAYS add formatted sources - remove any AI-generated sources section first
        # Format: [file_name](reference|source_type) for frontend parsing
        # reference = file_id for files, url for web_crawl
        # Remove any existing sources section (case-insensitive) - handles with or without preceding newline
        answer = re.sub(r'(?:^|\n)\s*\**\s*\bSources?\b:?\s*\**\s*(?:\n[\s\S]*)?$', '', answer, flags=re.IGNORECASE).strip()
        
        # Build and append formatted sources ONLY if not a generic response
        if not is_generic:
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

        return {"answer": answer, "is_generic": is_generic, "tokens_used": tokens_used}
