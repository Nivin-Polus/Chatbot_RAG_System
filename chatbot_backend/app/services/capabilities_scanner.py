"""
Knowledge Base Capabilities Scanner Service

This service analyzes the contents of a collection's vector store to understand
what topics and information it contains. It generates intelligent summaries
that can be used for chatbot introductions and capability descriptions.
"""

import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter
from sqlalchemy.orm import Session

from app.config import settings
from app.models.collection import Collection

logger = logging.getLogger("capabilities_scanner")


class CapabilitiesScanner:
    """
    Scans a collection's knowledge base to extract topics, categories,
    and generate capability summaries.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session
        self._rag_instance = None
    
    @property
    def rag(self):
        """Lazy load RAG instance to avoid circular imports."""
        if self._rag_instance is None:
            from app.core.rag import RAG
            self._rag_instance = RAG(db_session=self.db_session)
        return self._rag_instance
    
    def scan_collection(
        self,
        collection_id: str,
        max_chunks_to_sample: int = 200,
        use_ai_summary: bool = True
    ) -> Dict:
        """
        Scan a collection's knowledge base to understand its contents.
        
        Args:
            collection_id: The collection to scan
            max_chunks_to_sample: Maximum number of chunks to analyze
            use_ai_summary: Whether to use AI to generate a summary
            
        Returns:
            Dictionary containing:
            - topics: List of detected topics/categories
            - document_types: Types of documents in the KB
            - summary: Human-readable summary of KB contents
            - sample_questions: Example questions users can ask
            - total_documents: Count of unique documents
            - total_chunks: Total chunks in collection
        """
        logger.info(f"[CAPABILITIES] Starting scan for collection: {collection_id}")
        
        try:
            # Get vector store
            from app.core.vector_singleton import get_vector_store
            vector_store = get_vector_store()
            
            if not vector_store or not vector_store.client:
                logger.warning(f"[CAPABILITIES] Vector store not available for {collection_id}")
                return self._generate_fallback_capabilities(collection_id)
            
            # Sample chunks from the collection
            chunks = self._sample_chunks(vector_store, collection_id, max_chunks_to_sample)
            
            if not chunks:
                logger.warning(f"[CAPABILITIES] No chunks found for collection {collection_id}")
                return self._generate_fallback_capabilities(collection_id)
            
            # Extract metadata from chunks
            topics = self._extract_topics(chunks)
            document_types = self._extract_document_types(chunks)
            unique_sources = self._extract_unique_sources(chunks)
            
            # Get total counts
            total_chunks = len(chunks)
            total_documents = len(unique_sources)
            
            # Generate AI summary if enabled
            if use_ai_summary and topics:
                summary, sample_questions = self._generate_ai_summary(
                    topics=topics,
                    document_types=document_types,
                    sample_content=self._get_sample_content(chunks),
                    collection_id=collection_id
                )
            else:
                summary = self._generate_basic_summary(topics, document_types, total_documents)
                sample_questions = self._generate_basic_questions(topics)
            
            capabilities = {
                "topics": topics[:15],  # Limit to top 15 topics
                "document_types": document_types,
                "summary": summary,
                "sample_questions": sample_questions[:5],  # Limit to 5 sample questions
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "scanned_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"[CAPABILITIES] Scan complete. Found {len(topics)} topics, {total_documents} documents")
            
            return capabilities
            
        except Exception as e:
            logger.error(f"[CAPABILITIES] Error scanning collection {collection_id}: {e}")
            return self._generate_fallback_capabilities(collection_id)
    
    def _sample_chunks(
        self,
        vector_store,
        collection_id: str,
        limit: int
    ) -> List[Dict]:
        """Sample chunks from the vector store for analysis."""
        try:
            # Use Qdrant scroll to get chunks
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            # Build filter for collection
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="collection_id",
                        match=MatchValue(value=collection_id)
                    )
                ]
            )
            
            # Scroll through chunks
            chunks = []
            offset = None
            
            while len(chunks) < limit:
                result = vector_store.client.scroll(
                    collection_name=vector_store.collection_name,
                    scroll_filter=filter_condition,
                    limit=min(100, limit - len(chunks)),
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                points, next_offset = result
                
                if not points:
                    break
                
                for point in points:
                    chunks.append(point.payload)
                
                if next_offset is None:
                    break
                offset = next_offset
            
            logger.debug(f"[CAPABILITIES] Sampled {len(chunks)} chunks from {collection_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"[CAPABILITIES] Error sampling chunks: {e}")
            return []
    
    def _extract_topics(self, chunks: List[Dict]) -> List[str]:
        """Extract and rank topics from chunk metadata and content."""
        topic_counter = Counter()
        org_names = set()  # Track organization names separately
        
        for chunk in chunks:
            # Extract from page titles
            page_title = chunk.get("page_title", "")
            if page_title:
                # Extract organization name from title (e.g., "About Us - Polus Solutions")
                org_match = re.search(r'[-–|]\s*([A-Z][A-Za-z\s]+(?:Solutions|Inc|LLC|Corp|Company|Services)?)\s*$', page_title)
                if org_match:
                    org_names.add(org_match.group(1).strip())
                
                # Clean and add page title as topic
                clean_title = self._clean_topic(page_title)
                if clean_title and self._is_valid_topic(clean_title):
                    topic_counter[clean_title] += 2  # Weight titles higher
            
            # Extract from headers/sections
            section = chunk.get("section", "") or chunk.get("header", "")
            if section:
                clean_section = self._clean_topic(section)
                if clean_section and self._is_valid_topic(clean_section):
                    topic_counter[clean_section] += 1
            
            # Extract from file names (for uploaded documents)
            file_name = chunk.get("file_name", "")
            if file_name:
                # Remove extension and clean
                name_without_ext = re.sub(r'\.[^.]+$', '', file_name)
                clean_name = self._clean_topic(name_without_ext)
                if clean_name and self._is_valid_topic(clean_name):
                    topic_counter[clean_name] += 1
            
            # Extract meaningful keywords from content
            content = chunk.get("text", "")[:800]  # First 800 chars
            if content:
                keywords = self._extract_keywords(content)
                for kw in keywords:
                    if self._is_valid_topic(kw):
                        topic_counter[kw] += 0.5
        
        # Build final topic list
        ranked_topics = []
        
        # Add organization names first (high priority)
        for org in org_names:
            if self._is_valid_topic(org) and len(org) > 3:
                ranked_topics.append(org)
        
        # Add other topics
        for topic, count in topic_counter.most_common(100):
            if self._is_valid_topic(topic):
                # Avoid duplicates (case-insensitive)
                if not any(topic.lower() == t.lower() for t in ranked_topics):
                    ranked_topics.append(topic)
                    if len(ranked_topics) >= 20:
                        break
        
        return ranked_topics
    
    def _is_valid_topic(self, topic: str) -> bool:
        """Check if a topic string is valid and meaningful."""
        if not topic or len(topic) < 4:
            return False
        
        topic_lower = topic.lower()
        
        # Reject URL-like patterns
        if re.match(r'^https?', topic_lower):
            return False
        if 'http' in topic_lower or 'www' in topic_lower:
            return False
        if '.com' in topic_lower or '.edu' in topic_lower or '.org' in topic_lower:
            return False
        if re.search(r'[/\\]', topic):  # Contains path separators
            return False
        
        # Reject if mostly numbers or special chars
        letter_count = sum(1 for c in topic if c.isalpha())
        if letter_count < len(topic) * 0.6:
            return False
        
        # Reject generic/junk terms
        generic_terms = {
            "home", "page", "index", "untitled", "document", "file", "files",
            "section", "chapter", "introduction", "overview", "about", "more",
            "contact", "privacy", "terms", "login", "register", "search",
            "menu", "navigation", "header", "footer", "sidebar", "content",
            "click", "here", "read", "learn", "view", "see", "get", "under",
            "glossary", "archive", "archives", "category", "categories", "tag", "tags",
            "author", "date", "time", "posted", "comment", "comments", "share",
            "next", "previous", "back", "forward", "top", "bottom", "left", "right",
            "default", "main", "primary", "secondary", "new", "old", "latest",
            "sitesdefaultfiles", "uploads", "images", "assets", "media", "static",
        }
        
        if topic_lower in generic_terms:
            return False
        
        # Reject if looks like a file path component
        if topic_lower.startswith(('sites', 'default', 'files', 'uploads', 'assets')):
            return False
        
        # Reject very short single words (except known good ones)
        if len(topic) < 6 and ' ' not in topic:
            good_short = {'hr', 'it', 'api', 'faq', 'erp', 'crm', 'tax', 'mit'}
            if topic_lower not in good_short:
                return False
        
        return True
    
    def _clean_topic(self, text: str) -> str:
        """Clean and normalize a topic string."""
        if not text:
            return ""
        
        # Remove URLs
        text = re.sub(r'https?://[^\s]+', '', text)
        
        # Remove common suffixes like "- Company Name"
        text = re.sub(r'\s*[-|–]\s*[A-Z][A-Za-z\s]+$', '', text)
        
        # Remove numbering at start
        text = re.sub(r'^\d+\.\s*', '', text)
        
        # Remove special chars except hyphen, ampersand, and space
        text = re.sub(r'[^\w\s\-&]', ' ', text)
        
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove leading/trailing junk
        text = re.sub(r'^(the|a|an)\s+', '', text, flags=re.IGNORECASE)
        
        # Capitalize properly if all lowercase
        if text and text.islower():
            text = text.title()
        
        return text[:80].strip()
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extract potential topic keywords from content."""
        keywords = []
        
        # Find capitalized multi-word phrases (proper nouns, product names, etc.)
        # Examples: "Research Administration", "Grant Management", "Polus Solutions"
        matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', content)
        for m in matches:
            if len(m) > 8 and len(m) < 50:
                keywords.append(m)
        
        # Find common topic patterns
        topic_patterns = [
            r'\b([A-Z][a-z]+\s+(?:Management|Administration|Services|Policy|Policies|System|Process|Procedure))\b',
            r'\b((?:HR|IT|Tax|Grant|Research|Employee|Leave|Travel)\s+[A-Z][a-z]+)\b',
        ]
        
        for pattern in topic_patterns:
            matches = re.findall(pattern, content)
            keywords.extend(matches)
        
        # Deduplicate and limit
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)
        
        return unique_keywords[:8]
    
    def _extract_document_types(self, chunks: List[Dict]) -> List[str]:
        """Extract types of documents in the knowledge base."""
        type_counter = Counter()
        
        for chunk in chunks:
            source_type = chunk.get("source_type", "")
            
            if source_type == "web_crawl":
                type_counter["Web Pages"] += 1
            elif source_type == "file":
                file_name = chunk.get("file_name", "").lower()
                if file_name.endswith(".pdf"):
                    type_counter["PDF Documents"] += 1
                elif file_name.endswith((".doc", ".docx")):
                    type_counter["Word Documents"] += 1
                elif file_name.endswith((".xls", ".xlsx")):
                    type_counter["Excel Spreadsheets"] += 1
                elif file_name.endswith((".ppt", ".pptx")):
                    type_counter["PowerPoint Presentations"] += 1
                elif file_name.endswith(".txt"):
                    type_counter["Text Files"] += 1
                else:
                    type_counter["Documents"] += 1
            else:
                type_counter["Documents"] += 1
        
        return [doc_type for doc_type, _ in type_counter.most_common(5)]
    
    def _extract_unique_sources(self, chunks: List[Dict]) -> set:
        """Extract unique source documents/pages."""
        sources = set()
        
        for chunk in chunks:
            # Use file_id, url, or file_name as unique identifier
            source_id = (
                chunk.get("file_id") or 
                chunk.get("url") or 
                chunk.get("canonical_url") or
                chunk.get("file_name")
            )
            if source_id:
                sources.add(source_id)
        
        return sources
    
    def _get_sample_content(self, chunks: List[Dict], max_samples: int = 10) -> str:
        """Get sample content snippets for AI analysis."""
        samples = []
        seen_sources = set()
        
        for chunk in chunks:
            source = chunk.get("file_name") or chunk.get("page_title") or "Unknown"
            if source in seen_sources:
                continue
            seen_sources.add(source)
            
            content = chunk.get("text", "")[:300]
            if content:
                samples.append(f"[{source}]: {content}")
            
            if len(samples) >= max_samples:
                break
        
        return "\n\n".join(samples)
    
    def _generate_ai_summary(
        self,
        topics: List[str],
        document_types: List[str],
        sample_content: str,
        collection_id: str
    ) -> Tuple[str, List[str]]:
        """Use AI to generate a summary and sample questions."""
        try:
            prompt = f"""Analyze this knowledge base content and provide:
1. A brief summary (2-3 sentences) of what information this knowledge base contains
2. 5 example questions users could ask

Topics detected: {', '.join(topics[:10])}
Document types: {', '.join(document_types)}

Sample content from the knowledge base:
{sample_content[:2000]}

Respond in this exact JSON format:
{{
    "summary": "This knowledge base contains information about...",
    "sample_questions": [
        "Question 1?",
        "Question 2?",
        "Question 3?",
        "Question 4?",
        "Question 5?"
    ]
}}

Only return the JSON, no other text."""

            response_text, _ = self.rag.call_ai(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3
            )
            
            # Parse response
            response_text = response_text.strip()
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(response_text)
            summary = result.get("summary", "")
            questions = result.get("sample_questions", [])
            
            if summary and questions:
                return summary, questions
            
        except Exception as e:
            logger.warning(f"[CAPABILITIES] AI summary generation failed: {e}")
        
        # Fallback to basic generation
        return self._generate_basic_summary(topics, document_types, 0), self._generate_basic_questions(topics)
    
    def _generate_basic_summary(
        self,
        topics: List[str],
        document_types: List[str],
        total_documents: int
    ) -> str:
        """Generate a basic summary without AI."""
        if not topics:
            return "This knowledge base contains various documents and information."
        
        topic_str = ", ".join(topics[:5])
        doc_type_str = " and ".join(document_types[:2]) if document_types else "documents"
        
        return f"This knowledge base contains {doc_type_str} covering topics such as {topic_str}."
    
    def _generate_basic_questions(self, topics: List[str]) -> List[str]:
        """Generate basic sample questions from topics."""
        questions = []
        
        question_templates = [
            "What is {}?",
            "Tell me about {}",
            "How does {} work?",
            "What are the {} policies?",
            "Explain {}"
        ]
        
        for i, topic in enumerate(topics[:5]):
            template = question_templates[i % len(question_templates)]
            questions.append(template.format(topic.lower()))
        
        return questions
    
    def _generate_fallback_capabilities(self, collection_id: str) -> Dict:
        """Generate fallback capabilities when scanning fails."""
        return {
            "topics": [],
            "document_types": [],
            "summary": "I can help you find information from the knowledge base.",
            "sample_questions": [
                "What information do you have?",
                "Can you help me find something?"
            ],
            "total_documents": 0,
            "total_chunks": 0,
            "scanned_at": datetime.utcnow().isoformat(),
            "is_fallback": True
        }
    
    def update_collection_capabilities(
        self,
        collection_id: str,
        capabilities: Optional[Dict] = None,
        force_scan: bool = False
    ) -> bool:
        """
        Update a collection's capabilities in the database.
        
        Args:
            collection_id: Collection to update
            capabilities: Pre-computed capabilities (if None, will scan)
            force_scan: Force a new scan even if capabilities exist
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db_session:
            logger.error("[CAPABILITIES] No database session available")
            return False
        
        try:
            collection = self.db_session.query(Collection).filter(
                Collection.collection_id == collection_id
            ).first()
            
            if not collection:
                logger.error(f"[CAPABILITIES] Collection not found: {collection_id}")
                return False
            
            # Skip if recently scanned (within 1 hour) unless forced
            if not force_scan and collection.capabilities_last_scanned:
                from datetime import timedelta
                age = datetime.utcnow() - collection.capabilities_last_scanned.replace(tzinfo=None)
                if age < timedelta(hours=1):
                    logger.info(f"[CAPABILITIES] Skipping scan - recently scanned ({age})")
                    return True
            
            # Scan if no capabilities provided
            if capabilities is None:
                capabilities = self.scan_collection(collection_id)
            
            # Update collection
            collection.capabilities_summary = capabilities
            collection.capabilities_last_scanned = datetime.utcnow()
            
            self.db_session.commit()
            logger.info(f"[CAPABILITIES] Updated capabilities for {collection_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"[CAPABILITIES] Error updating collection capabilities: {e}")
            self.db_session.rollback()
            return False


# Singleton instance for easy access
_scanner_instance = None


def get_capabilities_scanner(db_session: Optional[Session] = None) -> CapabilitiesScanner:
    """Get or create a capabilities scanner instance."""
    global _scanner_instance
    if _scanner_instance is None or db_session is not None:
        _scanner_instance = CapabilitiesScanner(db_session=db_session)
    return _scanner_instance


def scan_and_update_collection(collection_id: str, db_session: Session, force: bool = False) -> Dict:
    """
    Convenience function to scan a collection and update its capabilities.
    
    Args:
        collection_id: Collection to scan
        db_session: Database session
        force: Force scan even if recently scanned
        
    Returns:
        The capabilities dictionary
    """
    scanner = CapabilitiesScanner(db_session=db_session)
    capabilities = scanner.scan_collection(collection_id)
    scanner.update_collection_capabilities(collection_id, capabilities, force_scan=force)
    return capabilities
