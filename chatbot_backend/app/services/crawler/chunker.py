# app/services/crawler/chunker.py
"""
Text Chunker for RAG
Splits content into optimally-sized chunks with metadata preservation.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import hashlib


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
            "char_count": self.char_count
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
            "chunk_index": self.chunk_index
        }


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
                        crawl_depth=crawl_depth
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
                        job_id, collection_id, timestamp, crawl_depth
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
                job_id, collection_id, timestamp, crawl_depth
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
        crawl_depth: int
    ) -> List[ContentChunk]:
        """Chunk a group of sections under the same header."""
        chunks = []
        
        # Combine section content
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
                crawl_depth=crawl_depth
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
