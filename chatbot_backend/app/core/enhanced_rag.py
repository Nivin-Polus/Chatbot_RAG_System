"""
enhanced_rag.py

Person-first RAG retrieval and answer generation.

This module provides drop-in replacements for your existing RAG functions
with person-first retrieval, source weighting, and entity-based answer modes.

Usage:
    from enhanced_rag import EnhancedRAG
    
    rag = EnhancedRAG(qdrant_client, embed_fn, llm_fn)
    answer = rag.answer_query("Who is the HR manager?", org="Polus Solutions")
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
import logging

from app.core.role_matcher import RoleMatcher

logger = logging.getLogger(__name__)


# ===== ENUMS =====

class QueryIntent(Enum):
    """Query intent classification."""
    PERSON_LOOKUP = "person"      # "who is X", "tell me about X"
    ROLE_LOOKUP = "role"          # "who is the HR manager"
    GENERAL = "general"           # Everything else


class AnswerMode(Enum):
    """Answer modes based on retrieved evidence."""
    PERSON_CONFIRMED = "person_confirmed"     # Person entity found
    ROLE_OWNER_FOUND = "role_owner_found"     # Role matched to person
    ROLE_NO_OWNER = "role_no_owner"           # Role exists but no owner
    NO_DATA = "no_data"                        # No relevant entities found
    GENERAL_INFO = "general_info"              # Non-entity query with data


# ===== DATA MODELS =====

@dataclass
class RetrievalResult:
    """Container for retrieval results and metadata."""
    chunks: List[Dict]
    intent: QueryIntent
    answer_mode: AnswerMode
    role_match: Optional[Dict] = None
    debug_info: Optional[Dict] = None


# ===== SOURCE WEIGHTING =====

SOURCE_WEIGHTS = {
    "about_us": 1.0,
    "team_page": 1.0,
    "leadership_page": 0.95,
    "profile_page": 0.9,
    "blog": 0.5,
    "job_posting": 0.3,  # Heavily penalize job postings
    "news": 0.6,
    "case_study": 0.7,
    "other": 0.6
}


# ===== MAIN CLASS =====

class EnhancedRAG:
    """
    Enhanced RAG with person-first retrieval and entity-based answer modes.
    
    This is designed to be a drop-in replacement for your existing RAG
    pipeline with minimal changes.
    """
    
    def __init__(
        self,
        qdrant_client,
        embed_fn: Callable[[str], List[float]],
        llm_fn: Callable[[str], str],
        collection_name: str = "knowledge_base",
        role_matcher_threshold: float = 0.6,
        person_search_threshold: float = 0.5
    ):
        """
        Initialize enhanced RAG.
        
        Args:
            qdrant_client: Initialized Qdrant client
            embed_fn: Function to generate embeddings
            llm_fn: Function to call LLM for answer generation
            collection_name: Qdrant collection name
            role_matcher_threshold: Threshold for role matching (0.6 recommended)
            person_search_threshold: Threshold for person entity search (0.5 recommended)
        """
        self.qdrant = qdrant_client
        self.embed_fn = embed_fn
        self.llm_fn = llm_fn
        self.collection_name = collection_name
        self.person_search_threshold = person_search_threshold
        
        # Initialize role matcher
        self.role_matcher = RoleMatcher(
            embed_fn=embed_fn,
            threshold=role_matcher_threshold
        )
    
    def answer_query(
        self,
        query: str,
        org: str,
        top_k: int = 10,
        debug: bool = False
    ) -> str:
        """
        Main entry point: Answer a query with person-first RAG.
        """
        # Step 1: Retrieve with person-first logic
        result = self.retrieve(query, org, top_k, debug)
        
        # Step 2: Generate answer based on mode
        answer = self._generate_answer(query, result)
        
        # Step 3: Log debug info if requested
        if debug:
            logger.info(f"Query: {query}")
            logger.info(f"Intent: {result.intent.value}")
            logger.info(f"Answer mode: {result.answer_mode.value}")
            logger.info(f"Chunks found: {len(result.chunks)}")
            if result.role_match:
                logger.info(f"Role match: {result.role_match}")
        
        return answer
    
    def retrieve(
        self,
        query: str,
        org: str,
        top_k: int = 10,
        debug: bool = False
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks with person-first logic.
        """
        # Detect intent
        intent = self._detect_intent(query)
        
        # Person/role queries: person-first search
        if intent in [QueryIntent.PERSON_LOOKUP, QueryIntent.ROLE_LOOKUP]:
            chunks = self._person_first_search(query, org, top_k)
            
            # Apply source weighting
            chunks = self._apply_source_weighting(chunks)
            
            # For role queries, try to match role
            role_match = None
            if intent == QueryIntent.ROLE_LOOKUP:
                role_match = self._match_role(query, chunks)
            
            # Determine answer mode
            answer_mode = self._determine_answer_mode(intent, chunks, role_match)
            
            return RetrievalResult(
                chunks=chunks,
                intent=intent,
                answer_mode=answer_mode,
                role_match=role_match
            )
        
        # General queries: normal search
        else:
            chunks = self._general_search(query, org, top_k)
            chunks = self._apply_source_weighting(chunks)
            
            answer_mode = (
                AnswerMode.GENERAL_INFO if chunks else AnswerMode.NO_DATA
            )
            
            return RetrievalResult(
                chunks=chunks,
                intent=intent,
                answer_mode=answer_mode
            )
    
    def _person_first_search(
        self,
        query: str,
        org: str,
        top_k: int
    ) -> List[Dict]:
        """
        Person-first search: search person entities first, fallback to general.
        """
        query_vector = self.embed_fn(query)
        
        # Step 1: Search person entities only
        person_results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter={
                "must": [
                    {"key": "entity_type", "match": {"value": "person"}},
                    {"key": "organization", "match": {"value": org}}
                ]
            },
            limit=top_k,
            score_threshold=self.person_search_threshold
        )
        
        # If we found person entities, use them
        if person_results:
            logger.info(f"[PERSON-FIRST] Found {len(person_results)} person entities")
            return self._qdrant_to_chunks(person_results)
        
        # Step 2: Fallback to general search if no persons found
        logger.info("[PERSON-FIRST] No person entities found, falling back to general search")
        return self._general_search(query, org, top_k)
    
    def _general_search(
        self,
        query: str,
        org: str,
        top_k: int
    ) -> List[Dict]:
        """General semantic search across all chunks."""
        query_vector = self.embed_fn(query)
        
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter={
                "must": [
                    {"key": "organization", "match": {"value": org}}
                ]
            },
            limit=top_k
        )
        
        return self._qdrant_to_chunks(results)
    
    def _match_role(self, query: str, chunks: List[Dict]) -> Optional[Dict]:
        """
        Match role query to person chunks using semantic similarity.
        """
        # Extract role from query
        role = self.role_matcher.extract_role_from_query(query)
        if not role:
            logger.warning(f"Could not extract role from query: {query}")
            return None
        
        # Find matching people
        matches = self.role_matcher.find_role_owners(role, chunks, top_k=5)
        
        if not matches:
            return None
        
        # Return best match with metadata
        best_chunk, best_score = matches[0]
        metadata = best_chunk.get("metadata", {})
        
        return {
            "person_name": metadata.get("person_name"),
            "person_title": metadata.get("person_title"),
            "organization": metadata.get("organization"),
            "linkedin_url": metadata.get("linkedin_url"),
            "email": metadata.get("email"),
            "match_score": best_score,
            "source_url": metadata.get("url")
        }
    
    def _apply_source_weighting(self, chunks: List[Dict]) -> List[Dict]:
        """
        Apply source priority weighting to chunk scores.
        """
        for chunk in chunks:
            source_type = chunk.get("metadata", {}).get("source_type", "other")
            weight = SOURCE_WEIGHTS.get(source_type, 0.5)
            
            # Store original score for debugging
            chunk["original_score"] = chunk.get("score", 0.0)
            chunk["source_weight"] = weight
            
            # Apply weight
            chunk["score"] = chunk.get("score", 0.0) * weight
        
        # Re-sort by weighted score
        chunks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        return chunks
    
    def _detect_intent(self, query: str) -> QueryIntent:
        """
        Detect query intent using simple rule-based classification.
        """
        query_lower = query.lower()
        
        # Person lookup patterns
        person_patterns = ["who is", "tell me about", "contact for"]
        
        # "What does X do" is usually a person query only if X is not the company
        # Simple heuristic: if it contains "the company" or "Polus", it's likely general
        is_what_does_person = query_lower.startswith("what does") and \
                              not any(c in query_lower for c in ["polus", "the company", "this company"])
        
        if any(p in query_lower for p in person_patterns) or is_what_does_person:
            # Check for role keywords
            role_keywords = [
                "manager", "head", "director", "ceo", "cto", "cfo",
                "lead", "specialist", "coordinator", "hr", "sales",
                "president", "vp", "chief", "officer"
            ]
            
            if any(role in query_lower for role in role_keywords):
                return QueryIntent.ROLE_LOOKUP
            
            return QueryIntent.PERSON_LOOKUP
        
        return QueryIntent.GENERAL
    
    def _determine_answer_mode(
        self,
        intent: QueryIntent,
        chunks: List[Dict],
        role_match: Optional[Dict] = None
    ) -> AnswerMode:
        """
        Determine answer mode based on retrieved ENTITIES.
        """
        # Check for person entities
        person_entities = [
            c for c in chunks
            if c.get("metadata", {}).get("entity_type") == "person"
        ]
        
        # Person lookup (e.g., "Who is Ramya A?")
        if intent == QueryIntent.PERSON_LOOKUP:
            return (
                AnswerMode.PERSON_CONFIRMED if person_entities
                else AnswerMode.NO_DATA
            )
        
        # Role lookup (e.g., "Who is the HR manager?")
        if intent == QueryIntent.ROLE_LOOKUP:
            if role_match and role_match.get("match_score", 0) > self.role_matcher.threshold:
                return AnswerMode.ROLE_OWNER_FOUND
            elif person_entities:
                return AnswerMode.ROLE_NO_OWNER
            else:
                return AnswerMode.NO_DATA
        
        # General queries
        return AnswerMode.GENERAL_INFO if chunks else AnswerMode.NO_DATA
    
    def _generate_answer(
        self,
        query: str,
        result: RetrievalResult
    ) -> str:
        """
        Generate answer based on mode and evidence.
        """
        mode = result.answer_mode
        chunks = result.chunks
        
        # ===== PERSON CONFIRMED =====
        if mode == AnswerMode.PERSON_CONFIRMED:
            person = chunks[0]["metadata"]
            
            answer = (
                f"{person.get('person_name', 'This person')} is the {person.get('person_title', 'employee')} "
                f"at {person.get('organization', 'the company')}."
            )
            
            if person.get("linkedin_url"):
                answer += f"\n\nLinkedIn: {person['linkedin_url']}"
            
            return answer
        
        # ===== ROLE OWNER FOUND =====
        if mode == AnswerMode.ROLE_OWNER_FOUND:
            person = result.role_match
            
            answer = (
                f"The {person.get('person_title', 'role')} at {person.get('organization', 'the company')} "
                f"is {person.get('person_name', 'identified')}."
            )
            
            if person.get("linkedin_url"):
                answer += f"\n\nLinkedIn: {person['linkedin_url']}"
            
            return answer
        
        # ===== ROLE NO OWNER =====
        if mode == AnswerMode.ROLE_NO_OWNER:
            org = chunks[0]["metadata"].get("organization", "the company")
            return (
                f"I found information about {org}, but I don't have "
                f"details about who currently holds this specific role."
            )
        
        # ===== NO DATA =====
        if mode == AnswerMode.NO_DATA:
            return "I don't have information about this in my knowledge base."
        
        # ===== GENERAL INFO (Use LLM) =====
        if mode == AnswerMode.GENERAL_INFO:
            context = "\n\n".join([
                c.get("text", "") for c in chunks[:5]
            ])
            
            prompt = f"""Answer the question based on the context below.

Context:
{context}

Question: {query}

Answer:"""
            
            return self.llm_fn(prompt)
        
        return "Unable to generate answer."
    
    def _qdrant_to_chunks(self, qdrant_results) -> List[Dict]:
        """Convert Qdrant results to chunk format."""
        chunks = []
        for result in qdrant_results:
            payload = getattr(result, 'payload', {})
            score = getattr(result, 'score', 0.0)
            chunks.append({
                "text": payload.get("text", ""),
                "metadata": payload.get("metadata", {}),
                "score": score
            })
        return chunks
