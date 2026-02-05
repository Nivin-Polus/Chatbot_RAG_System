# app/services/crawler/chunker.py
"""
Text Chunker for RAG
Splits content into optimally-sized chunks with metadata preservation.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any
from datetime import datetime
import hashlib
from .config import CrawlConfig


@dataclass
class ContentChunk:
    """A chunk of content ready for vector embedding."""
    
    chunk_id: str
    text: str
    
    # Source metadata
    url: str
    canonical_url: str
    page_title: str
    
    # Section metadata
    section_header: Optional[str] = None
    parent_headers: List[str] = field(default_factory=list)
    block_type: str = "paragraph"
    
    # Positioning
    chunk_index: int = 0
    total_chunks: int = 1
    
    # Crawl metadata
    crawl_job_id: str = ""
    collection_id: str = ""
    crawl_timestamp: str = ""
    crawl_depth: int = 0
    
    # Stats
    word_count: int = 0
    char_count: int = 0
    
    # P1 FIX: Domain tag
    domain: str = "general"
    
    # FIX 15: Person Entity Fields
    entity_type: str = "content" # content | person | image
    person_name: Optional[str] = None
    person_title: Optional[str] = None
    
    # FIX 1: Organization Field (Mandatory)
    organization: Optional[str] = None
    
    def __post_init__(self):
        self.word_count = len(self.text.split())
        self.char_count = len(self.text)
        if not self.chunk_id:
            self.chunk_id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate a unique chunk ID."""
        content = f"{self.url}:{self.chunk_index}:{self.text[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage/API."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "page_title": self.page_title,
            "section_header": self.section_header,
            "parent_headers": self.parent_headers,
            "block_type": self.block_type,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "crawl_job_id": self.crawl_job_id,
            "collection_id": self.collection_id,
            "crawl_timestamp": self.crawl_timestamp,
            "crawl_depth": self.crawl_depth,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "domain": self.domain, # P1 FIX
            "organization": self.organization, # FIX 1
            "entity_type": self.entity_type, # FIX 15
            "person_name": self.person_name,
            "person_title": self.person_title
        }
    
    def to_vector_metadata(self) -> dict:
        """Get metadata for vector database storage."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,  # CRITICAL: Include text for RAG retrieval
            "url": self.url,
            "canonical_url": self.canonical_url,
            "page_title": self.page_title,
            "file_name": self.page_title or self.url,  # For RAG sources display compatibility
            "section_header": self.section_header or "",
            "parent_headers": " > ".join(self.parent_headers),
            "block_type": self.block_type,
            "collection_id": self.collection_id,
            "crawl_job_id": self.crawl_job_id,
            "crawl_timestamp": self.crawl_timestamp,
            "source_type": "web_crawl",
            "chunk_index": self.chunk_index,
            "domain": self.domain, # P1 FIX
            "organization": self.organization, # FIX 1
            "entity_type": self.entity_type, # FIX 15
            "person_name": self.person_name,
            "person_title": self.person_title
        }


@dataclass
class EnhancedContentChunk(ContentChunk):
    """
    Extended chunk with Phase 2 metadata for enhanced retrieval.
    Includes hierarchical linking, rich metadata, and content classification.
    """
    
    # Phase 2: Hierarchical linking
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = field(default_factory=list)
    is_parent_chunk: bool = False  # Explicit flag for filtering
    
    # Phase 2: Chunk classification
    chunk_type: str = "narrative"  # narrative | reference | code | person_profile
    section_id: Optional[str] = None   # Hashed section path for grouping
    
    # Phase 2: Page-level metadata (inherited)
    page_type: str = "general"
    page_confidence: float = 0.0
    content_quality_score: float = 0.0
    
    # Phase 2: Person metadata (for person_profile chunks)
    person_name: Optional[str] = None
    person_title: Optional[str] = None
    person_confidence: Optional[float] = None
    
    # Phase 3: Organizational Context (Fix 8)
    organization_context: Optional[str] = "site_owner" # site_owner | external
    person_type: Optional[str] = "internal"           # internal | external_reference
    confidence_score: float = 1.0                     # numeric confidence (0-1)
    
    # FIX 1: Organization Field (Already added in base, but emphasizing overriding rules if needed)
    # Inherits from ContentChunk

    
    # Phase 2: Entities and summary
    entities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary including Phase 2 fields."""
        base = super().to_dict()
        base.update({
            "parent_chunk_id": self.parent_chunk_id,
            "child_chunk_ids": self.child_chunk_ids,
            "is_parent_chunk": self.is_parent_chunk,
            "chunk_type": self.chunk_type,
            "section_id": self.section_id,
            "page_type": self.page_type,
            "page_confidence": self.page_confidence,
            "content_quality_score": self.content_quality_score,
            "person_name": self.person_name,
            "person_title": self.person_title,
            "person_confidence": self.person_confidence,
            "organization_context": self.organization_context,
            "person_type": self.person_type,
            "confidence_score": self.confidence_score,
            "entities": self.entities,
            "keywords": self.keywords,
            "summary": self.summary,
            "organization": self.organization # FIX 1
        })
        return base
        
    def to_vector_metadata(self) -> dict:
        """Get metadata for vector database storage with Phase 2 fields."""
        # Start with base metadata
        base = super().to_vector_metadata()
        
        # Add Phase 2 fields
        enhanced = {
            "parent_chunk_id": self.parent_chunk_id,
            "is_parent_chunk": self.is_parent_chunk,
            "chunk_type": self.chunk_type,
            "section_id": self.section_id,
            "page_type": self.page_type,
            "page_confidence": self.page_confidence,
            "content_quality_score": self.content_quality_score,
            "person_name": self.person_name,
            "person_title": self.person_title,
            "person_confidence": self.person_confidence,
            "organization_context": self.organization_context,
            "person_type": self.person_type,
            "organization_context": self.organization_context,
            "person_type": self.person_type,
            "confidence_score": self.confidence_score,
            "organization": self.organization # FIX 1
        }
        
        # Merge and filter None values
        base.update(enhanced)
        return {k: v for k, v in base.items() if v is not None}


class TextChunker:
    """
    Splits extracted content into chunks optimized for RAG.
    
    Uses semantic boundaries (sentences, paragraphs) rather than
    arbitrary character splits for better retrieval quality.
    """
    
    def __init__(
        self,
        chunk_size: int = 800,  # Target tokens (approx 4 chars per token)
        chunk_overlap: int = 100,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.chars_per_token = 4  # Rough approximation
    
    def chunk_page(
        self,
        extracted_content: Dict,
        job_id: str,
        collection_id: str,
        crawl_depth: int = 0
    ) -> List[ContentChunk]:
        """
        Create chunks from extracted page content.
        
        Args:
            extracted_content: Output from ContentExtractor.extract()
            job_id: Crawl job ID
            collection_id: Target collection ID
            crawl_depth: Depth from start URL
            
        Returns:
            List of ContentChunk objects
        """
        chunks = []
        timestamp = datetime.utcnow().isoformat()
        
        url = extracted_content.get("url", "")
        canonical_url = extracted_content.get("canonical_url", url)
        page_title = extracted_content.get("title", "")
        # FIX 1: Get page-level organization
        organization = extracted_content.get("organization")
        
        # FIX 15: Process Person Entities (even in TextChunker)
        people = extracted_content.get("people", [])
        if people:
            person_chunks = self._create_person_chunks(
                people, url, canonical_url, page_title,
                job_id, collection_id, timestamp, crawl_depth,
                organization
            )
            chunks.extend(person_chunks)
        
        sections = extracted_content.get("sections", [])
        
        if not sections:
            # Fallback: chunk raw text
            raw_text = extracted_content.get("raw_text", "")
            if raw_text:
                text_chunks = self._split_text(raw_text)
                for i, text in enumerate(text_chunks):
                    chunks.append(ContentChunk(
                        chunk_id="",
                        text=text,
                        url=url,
                        canonical_url=canonical_url,
                        page_title=page_title,
                        chunk_index=i,
                        total_chunks=len(text_chunks),
                        crawl_job_id=job_id,
                        collection_id=collection_id,
                        crawl_timestamp=timestamp,
                        crawl_depth=crawl_depth,
                        domain="general", # Default for raw text fallback
                        organization=organization # FIX 1
                    ))
            return chunks
        
        # Group sections by their parent header
        current_group = []
        current_header = None
        current_parents = []
        
        for section in sections:
            if section.block_type == "header":
                # Flush current group
                if current_group:
                    group_chunks = self._chunk_section_group(
                        current_group,
                        current_header,
                        current_parents,
                        url, canonical_url, page_title,
                        job_id, collection_id, timestamp, crawl_depth,
                        organization # FIX 1 passed
                    )
                    chunks.extend(group_chunks)
                    current_group = []
                
                current_header = section.header
                current_parents = section.parent_headers.copy()
                
            else:
                current_group.append(section)
        
        # Flush remaining group
        if current_group:
            group_chunks = self._chunk_section_group(
                current_group,
                current_header,
                current_parents,
                url, canonical_url, page_title,
                job_id, collection_id, timestamp, crawl_depth,
                organization # FIX 1 passed
            )
            chunks.extend(group_chunks)
        
        # Update total_chunks count
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.total_chunks = total
        
        return chunks
    
    def _chunk_section_group(
        self,
        sections: List,
        header: Optional[str],
        parent_headers: List[str],
        url: str,
        canonical_url: str,
        page_title: str,
        job_id: str,
        collection_id: str,
        timestamp: str,

        crawl_depth: int,
        organization: Optional[str] # FIX 1
    ) -> List[ContentChunk]:
        """Chunk a group of sections under the same header."""
        chunks = []
        
        # Determine domain from sections (majority or first)
        domain = "general"
        if sections:
             # Use the first section's domain (assuming page-level consistency)
             domain = sections[0].domain if hasattr(sections[0], 'domain') else sections[0].get('domain', 'general')
        combined_text = ""
        block_type = "paragraph"
        
        for section in sections:
            if section.content:
                if combined_text:
                    combined_text += "\n\n"
                combined_text += section.content
                
                # Use the most specific block type
                if section.block_type in ["faq", "table", "code"]:
                    block_type = section.block_type
        
        if not combined_text or len(combined_text) < self.min_chunk_size:
            return chunks
        
        # Add header context to chunks
        if header:
            header_prefix = f"Section: {header}\n\n"
        else:
            header_prefix = ""
        
        # Split into appropriately sized chunks
        text_chunks = self._split_text(combined_text)
        
        for text in text_chunks:
            full_text = header_prefix + text if header_prefix else text
            
            chunks.append(ContentChunk(
                chunk_id="",
                text=full_text,
                url=url,
                canonical_url=canonical_url,
                page_title=page_title,
                section_header=header,
                parent_headers=parent_headers,
                block_type=block_type,
                crawl_job_id=job_id,
                collection_id=collection_id,
                crawl_timestamp=timestamp,
                crawl_depth=crawl_depth,
                domain=domain, # P1 FIX
                organization=organization # FIX 1
            ))
        
        return chunks
    
    def _split_text(self, text: str) -> List[str]:
        """
        Split text into chunks respecting semantic boundaries.
        
        Uses sentence boundaries when possible, falls back to
        paragraph or word boundaries.
        """
        target_chars = self.chunk_size * self.chars_per_token
        overlap_chars = self.chunk_overlap * self.chars_per_token
        
        if len(text) <= target_chars:
            return [text] if len(text) >= self.min_chunk_size else []
        
        chunks = []
        
        # Split into sentences
        sentences = self._split_into_sentences(text)
        
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            if current_length + sentence_length > target_chars and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                if len(chunk_text) >= self.min_chunk_size:
                    chunks.append(chunk_text)
                
                # Start new chunk with overlap
                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    if overlap_length + len(s) > overlap_chars:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_length += len(s)
                
                current_chunk = overlap_sentences
                current_length = overlap_length
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add remaining content
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(chunk_text)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Handle common abbreviations
        text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|Corp|vs|etc)\.\s', r'\1<ABBR> ', text)
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Restore abbreviations
        sentences = [s.replace('<ABBR>', '.') for s in sentences]
        

        # Filter empty sentences
        return [s.strip() for s in sentences if s.strip()]

    
    def _create_person_chunks(
        self,
        people: List[Dict],
        url: str,
        canonical_url: str,
        page_title: str,
        job_id: str,
        collection_id: str,
        timestamp: str,
        crawl_depth: int,
        organization: Optional[str]
    ) -> List[ContentChunk]:
        """Create chunks for person entities."""
        chunks = []
        for i, person in enumerate(people):
            # Format text for retrieval
            text_parts = [f"Person: {person.get('name', 'Unknown')}"]
            
            if person.get('title'):
                text_parts.append(f"Title: {person['title']}")
            
            # Use 'works_for' or fallback to organization
            org = person.get('works_for') or organization
            if org:
                text_parts.append(f"Company: {org}")
                
            if person.get('description'):
                text_parts.append(f"Bio: {person['description']}")
            
            # Add extracted entities as text for better retrieval
            if person.get('social_links'):
                for platform, link in person['social_links'].items():
                    text_parts.append(f"{platform.title()}: {link}")
                    
            full_text = "\n".join(text_parts)
            
            # Generate ID based on name and URL to prevent duplicates
            chunk_id = hashlib.sha256(f"person:{url}:{person.get('name')}".encode()).hexdigest()[:16]
            
            chunks.append(ContentChunk(
                chunk_id=chunk_id,
                text=full_text,
                url=url,
                canonical_url=canonical_url,
                page_title=page_title,
                chunk_index=i,  
                total_chunks=len(people),
                crawl_job_id=job_id,
                collection_id=collection_id,
                crawl_timestamp=timestamp,
                crawl_depth=crawl_depth,
                domain="general",
                organization=org,
                entity_type="person",
                person_name=person.get("name"),
                person_title=person.get("title")
            ))
            
        return chunks


class SemanticChunker:
    """
    Phase 2 semantic chunker with hierarchical support.
    
    Splits content based on structure (headings, paragraphs) rather than just text length.
    Supports hierarchical parent/child chunks and specialized person extraction.
    """
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.chunk_sizes = config.CHUNK_SIZES
    
    def chunk_page(
        self,
        extracted_content: Dict,
        job_id: str,
        collection_id: str,
        crawl_depth: int = 0
    ) -> List[EnhancedContentChunk]:
        """
        Create hierarchical chunks from extracted content in Phase 2 pipeline.
        
        Returns both parent and child chunks with proper linking.
        """
        chunks = []
        timestamp = datetime.utcnow().isoformat()
        
        # Extract base metadata
        url = extracted_content.get("url", "")
        canonical_url = extracted_content.get("canonical_url", url)
        page_title = extracted_content.get("title", "")
        
        # FIX 1: Get page-level organization
        organization = extracted_content.get("organization")
        
        # Extract Phase 1 metadata
        page_meta = extracted_content.get("page_type", {})
        page_type = page_meta.get("type", "general")
        page_confidence = page_meta.get("confidence", 0.0)
        
        # 1. Handle Person-Specific Chunking
        if self.config.ENABLE_PERSON_CHUNKING:
            people = extracted_content.get("people", [])
            for person in people:
                person_chunk = self._create_person_chunk(
                    person, 
                    url, canonical_url, page_title, 
                    page_type, page_confidence,
                    job_id, collection_id, timestamp, crawl_depth,
                    organization # FIX 1 passed
                )
                chunks.append(person_chunk)
        
        # 2. Get content sections
        sections = extracted_content.get("sections", [])
        if not sections:
            # Fallback to text splitting if no sections
            return chunks  # Return whatever we extracted so far (e.g. people)
            
        # 3. Create Hierarchical Chunks
        if self.config.ENABLE_HIERARCHICAL_CHUNKING:
            # Fix: Separate person profiles from narrative sections to prevent generic grouping
            narrative_sections = []
            
            for section in sections:
                meta = section.get('metadata', {})
                # Check for person_profile type (Fix 6 integration)
                if meta.get('type') == 'person_profile' or meta.get('doc_type') == 'person_profile':
                    profile_chunk = self._create_section_profile_chunk(
                        section, 
                        url, canonical_url, page_title,
                        page_type, page_confidence,
                        job_id, collection_id, timestamp, crawl_depth,
                        organization # FIX 1 passed
                    )
                    chunks.append(profile_chunk)
                else:
                    narrative_sections.append(section)

            parent_chunks, child_chunks = self._create_hierarchical_chunks(
                narrative_sections,
                url, canonical_url, page_title,
                page_type, page_confidence,
                job_id, collection_id, timestamp, crawl_depth,
                organization # FIX 1 passed
            )
            chunks.extend(parent_chunks)
            chunks.extend(child_chunks)
            
        else:
            # TODO: Non-hierarchical semantic fallback if needed
            # For now, we assume hierarchy is preferred in Phase 2
            pass
            
        return chunks

    def _create_person_chunk(
        self, 
        person: Dict,
        url: str, canonical_url: str, page_title: str,
        page_type: str, page_confidence: float,
        job_id: str, collection_id: str, timestamp: str, crawl_depth: int,
        organization: Optional[str] # FIX 1
    ) -> EnhancedContentChunk:
        """Create a dedicated chunk for a person entity."""
        # Format text for retrieval
        text_parts = [f"Person: {person.get('name', 'Unknown')}"]
        
        if person.get('title'):
            text_parts.append(f"Title: {person['title']}")
            
        if person.get('works_for'):
            text_parts.append(f"Company: {person['works_for']}")
            
        if person.get('description'):
            text_parts.append(f"Bio: {person['description']}")
            
        if person.get('email'):
            text_parts.append(f"Contact: {person['email']}")
            
        socials = person.get('social_links', {})
        if socials:
            links = ", ".join([f"{k.title()}: {v}" for k, v in socials.items()])
            text_parts.append(f"Social Links: {links}")
            
        full_text = "\n".join(text_parts)
        
        # Generate ID based on name and URL
        chunk_id = hashlib.sha256(f"person:{url}:{person.get('name')}".encode()).hexdigest()[:16]
        
        return EnhancedContentChunk(
            chunk_id=chunk_id,
            text=full_text,
            url=url,
            canonical_url=canonical_url,
            page_title=page_title,
            
            # Phase 2 Specifics
            chunk_type="person_profile",
            page_type=page_type,
            page_confidence=page_confidence,
            person_name=person.get("name"),
            person_title=person.get("title"),
            person_confidence=person.get("confidence"),
            
            # Metadata
            crawl_job_id=job_id,
            collection_id=collection_id,
            crawl_timestamp=timestamp,
            crawl_depth=crawl_depth,
            
            # Stats
            word_count=len(full_text.split()),

            char_count=len(full_text),
            
            # FIX 3: Inherit from person object (which got it from content_extractor)
            organization=person.get("organization") or organization, # Prefer person's copy (Fix 3)
            
            # FIX 15: Set entity type
            entity_type="person"
        )

    def _create_section_profile_chunk(
        self,
        section: Dict,
        url: str, canonical_url: str, page_title: str,
        page_type: str, page_confidence: float,
        job_id: str, collection_id: str, timestamp: str, crawl_depth: int,
        organization: Optional[str] # FIX 1
    ) -> EnhancedContentChunk:
        """Create a dedicated chunk for a person profile section (Fix 6)."""
        meta = section.get('metadata', {})
        text = section.get('text', '')
        
        # Generate stable ID
        chunk_id = hashlib.sha256(f"profile:{url}:{meta.get('name')}".encode()).hexdigest()[:16]
        
        return EnhancedContentChunk(
            chunk_id=chunk_id,
            text=text,
            url=url,
            canonical_url=canonical_url,
            page_title=page_title,
            section_header=section.get('heading'),
            
            # Phase 2 Specifics
            chunk_type="person_profile",
            page_type=page_type,
            page_confidence=page_confidence,
            
            # Map metadata
            person_name=meta.get("name"),
            person_title=meta.get("title"),
            person_confidence=meta.get("confidence") == "high",
            organization_context=meta.get("organization_context", "site_owner"),
            person_type=meta.get("person_type", "internal"),
            confidence_score=meta.get("confidence_score", 1.0),
            
            # Metadata
            crawl_job_id=job_id,
            collection_id=collection_id,
            crawl_timestamp=timestamp,
            crawl_depth=crawl_depth,
            
            # Stats
            word_count=len(text.split()),
            char_count=len(text),
            
            # FIX 1
            organization=meta.get("organization") or organization
        )

    def _create_hierarchical_chunks(
        self,
        sections: List[Dict],
        url: str, canonical_url: str, page_title: str,
        page_type: str, page_confidence: float,
        job_id: str, collection_id: str, timestamp: str, crawl_depth: int,
        organization: Optional[str] # FIX 1
    ) -> Tuple[List[EnhancedContentChunk], List[EnhancedContentChunk]]:
        """
        Create parent and child chunks with linking.
        Parent chunks group content under headings (~1500 tokens).
        Child chunks split parents into smaller pieces (400-600 tokens).
        """
        parent_chunks = []
        child_chunks = []
        
        # Group sections by parent header to form valid Parent Chunks
        grouped_sections = self._group_by_parent_header(sections)
        
        for group in grouped_sections:
            # 1. Create Parent Chunk
            parent_text = self._combine_section_text(group)
            if len(parent_text) < 50: # Skip empty/tiny groups
                continue
                
            parent_id = hashlib.sha256(f"parent:{url}:{parent_text[:50]}".encode()).hexdigest()[:16]
            section_header = group[0].get('header') if group else None
            section_path_str = str(section_header) if section_header else "root"
            section_id = hashlib.sha256(section_path_str.encode()).hexdigest()[:12]
            
            parent_chunk = EnhancedContentChunk(
                chunk_id=parent_id,
                text=parent_text,
                url=url,
                canonical_url=canonical_url,
                page_title=page_title,
                section_header=section_header,
                
                # Phase 2
                is_parent_chunk=True,
                chunk_type="narrative", # Default, refined later if mostly code
                section_id=section_id,
                page_type=page_type,
                page_confidence=page_confidence,
                
                # Metadata
                crawl_job_id=job_id,
                collection_id=collection_id,
                crawl_timestamp=timestamp,
                crawl_depth=crawl_depth,
                
                word_count=len(parent_text.split()),
    
                char_count=len(parent_text),
                
                # FIX 1
                organization=organization
            )
            
            # 2. Create Child Chunks from this Parent
            children = self._split_parent_into_children(
                parent_text, parent_chunk, 
                self.config.CHILD_CHUNK_SIZE_RANGE
            )
            
            # 3. Link them
            parent_chunk.child_chunk_ids = [c.chunk_id for c in children]
            
            # 4. Apply semantic overlap to children
            children = self._apply_semantic_overlap(children)
            
            parent_chunks.append(parent_chunk)
            child_chunks.extend(children)
            
        return parent_chunks, child_chunks

    def _group_by_parent_header(self, sections: List[Dict]) -> List[List[Dict]]:
        """
        Group sections that belong to the same logical parent block.
        Currently groups by h1/h2 boundaries until size limit reached.
        """
        groups = []
        current_group = []
        current_token_count = 0
        max_tokens = self.config.PARENT_CHUNK_SIZE
        
        for section in sections:
            # Assuming 'section' is a dict from StructuredSection.to_dict()
            content = section.get('text', '')
            tokens = len(content.split()) # Rough approx
            
            # Start new group if explicit major header switch OR too big
            # For Phase 1 compatibility, we rely on the header field
            is_major_header = section.get('heading_level', 0) <= 2
            
            if is_major_header and current_group and current_token_count > 100:
                groups.append(current_group)
                current_group = []
                current_token_count = 0
            
            current_group.append(section)
            current_token_count += tokens
            
            # Soft limit check
            if current_token_count > max_tokens:
                groups.append(current_group)
                current_group = []
                current_token_count = 0
        
        if current_group:
            groups.append(current_group)
            
        return groups

    def _combine_section_text(self, sections: List[Dict]) -> str:
        """Combine text from multiple sections for a parent chunk."""
        return "\n\n".join([s.get('text', '') for s in sections if s.get('text')])

    def _split_parent_into_children(
        self, 
        text: str, 
        parent: EnhancedContentChunk,
        size_range: Tuple[int, int]
    ) -> List[EnhancedContentChunk]:
        """Split parent text into smaller child chunks."""
        min_tokens, max_tokens = size_range
        # Rough char approximation (4 chars/token)
        max_chars = max_tokens * 4
        min_chars = min_tokens * 4
        
        # Use Semantic Splitting (Paragraphs > Sentences)
        # We re-use logic similar to TextChunker but more aggressive on semantic boundaries
        
        # Simple splitting for now - refine with regex if needed
        # Split by multiple newlines (paragraphs), handling messy whitespace
        paragraphs = re.split(r'\n{2,}', text)
        
        children = []
        current_text_parts = []
        current_len = 0
        
        chunk_idx = 0
        
        for para in paragraphs:
            para_len = len(para)
            
            if current_len + para_len > max_chars and current_text_parts:
                # Flush current chunk
                child_text = "\n\n".join(current_text_parts)
                children.append(self._create_child_chunk_from_parent(child_text, parent, chunk_idx))
                chunk_idx += 1
                current_text_parts = []
                current_len = 0
            
            if para_len > max_chars:
                 # Huge paragraph, force sentence split (fallback)
                 # Re-using the logic conceptually, implementing inline for simplicity
                 # or could use helper method
                 sentences = re.split(r'(?<=[.!?])\s+', para)
                 for sent in sentences:
                     if current_len + len(sent) > max_chars and current_text_parts:
                         child_text = " ".join(current_text_parts)
                         children.append(self._create_child_chunk_from_parent(child_text, parent, chunk_idx))
                         chunk_idx += 1
                         current_text_parts = []
                         current_len = 0
                     current_text_parts.append(sent)
                     current_len += len(sent)
            else:
                current_text_parts.append(para)
                current_len += para_len
        
        # Flush remaining
        if current_text_parts:
            child_text = "\n\n".join(current_text_parts)
            children.append(self._create_child_chunk_from_parent(child_text, parent, chunk_idx))
            
        return children

    def _create_child_chunk_from_parent(
        self, 
        text: str, 
        parent: EnhancedContentChunk,
        idx: int
    ) -> EnhancedContentChunk:
        """Helper to create child object inheriting parent metadata."""
        child_id = hashlib.sha256(f"child:{parent.chunk_id}:{idx}".encode()).hexdigest()[:16]
        
        return EnhancedContentChunk(
            chunk_id=child_id,
            text=text,
            url=parent.url,
            canonical_url=parent.canonical_url,
            page_title=parent.page_title,
            section_header=parent.section_header,
            
            # Linking
            parent_chunk_id=parent.chunk_id,
            is_parent_chunk=False,
            
            # Phase 2 metadata
            chunk_type=parent.chunk_type,
            section_id=parent.section_id,
            page_type=parent.page_type,
            page_confidence=parent.page_confidence,
            
            # Sub-chunk index
            chunk_index=idx,
            
            # Stats
            word_count=len(text.split()),
            char_count=len(text),
            
            # Pass through job IDs
            crawl_job_id=parent.crawl_job_id,
            collection_id=parent.collection_id,
            crawl_timestamp=parent.crawl_timestamp,
            crawl_depth=parent.crawl_depth
        )

    def _apply_semantic_overlap(self, chunks: List[EnhancedContentChunk]) -> List[EnhancedContentChunk]:
        """
        Apply overlap between consecutive child chunks.
        Only overlaps at narrative boundaries. 
        Respects section_id to prevent bleeding across logical sections.
        """
        if not chunks or len(chunks) < 2:
            return chunks
            
        overlap_ratio = self.config.SEMANTIC_OVERLAP_RATIO
        
        for i in range(1, len(chunks)):
            prev = chunks[i-1]
            curr = chunks[i]
            
            # Only overlap if:
            # 1. Not a person profile (handled separately)
            # 2. Same section ID (don't cross logical boundaries)
            # 3. Same parent (implied by section_id usually, but explicit check good)
            if prev.chunk_type == "person_profile" or curr.chunk_type == "person_profile":
                continue
                
            if prev.section_id != curr.section_id:
                continue
            
            # Calculate overlap
            # Take last N characters/tokens from prev
            overlap_len = int(prev.char_count * overlap_ratio)
            overlap_text = prev.text[-overlap_len:]
            
            # Try to find a clean break in the overlap text (newline or sentence end)
            # This is a simple improvement to avoid cutting words
            clean_break = -1
            if '\n' in overlap_text:
                clean_break = overlap_text.find('\n') 
            elif '. ' in overlap_text:
                clean_break = overlap_text.find('. ')
            
            if clean_break != -1:
                overlap_text = overlap_text[clean_break+1:].strip()
            
            # Prepend to current
            if overlap_text:
                curr.text = overlap_text + "\n" + curr.text
                curr.char_count = len(curr.text)
                curr.word_count = len(curr.text.split())
                
        return chunks
