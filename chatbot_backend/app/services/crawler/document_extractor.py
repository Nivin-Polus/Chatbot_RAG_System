# app/services/crawler/document_extractor.py
"""
Document Extractor for Web Crawler
Downloads and extracts text from PDF and Word documents.
"""

import os
import logging
import requests
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse, unquote

logger = logging.getLogger("document_extractor")


def download_document(url: str, download_dir: str, timeout: int = 30) -> Optional[str]:
    """
    Download a document from a URL to a local directory.
    
    Args:
        url: URL of the document to download
        download_dir: Directory to save the document
        timeout: Request timeout in seconds
        
    Returns:
        Absolute path to the downloaded file, or None if download failed
    """
    try:
        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)
        
        # Extract filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(unquote(parsed_url.path))
        
        # If no filename or no extension, generate one
        if not filename or '.' not in filename:
            # Use URL hash as filename with .pdf default
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            filename = f"document_{url_hash}.pdf"
        
        # Construct file path
        file_path = os.path.join(download_dir, filename)
        
        # Download the file
        logger.info(f"Downloading document: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Check file size (skip if too large - over 100MB)
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 100 * 1024 * 1024:  # 100 MB
            logger.warning(f"Document too large ({int(content_length) / (1024*1024):.1f}MB): {url}")
            return None
        
        # Write to file
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Downloaded to: {file_path} ({os.path.getsize(file_path)} bytes)")
        return file_path
        
    except requests.exceptions.Timeout:
        logger.error(f"Download timeout for {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading {url}: {e}")
        return None


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    try:
        from pypdf import PdfReader
        
        logger.info(f"Extracting text from PDF: {file_path}")
        reader = PdfReader(file_path)
        
        text_parts = []
        for page_num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(text)
            except Exception as e:
                logger.warning(f"Failed to extract page {page_num} from PDF: {e}")
                continue
        
        full_text = '\n\n'.join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters from {len(reader.pages)} pages")
        
        return full_text
        
    except ImportError:
        logger.error("pypdf library not installed. Install with: pip install pypdf")
        return ""
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {file_path}: {e}")
        return ""


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from a DOCX file.
    
    Args:
        file_path: Path to the DOCX file
        
    Returns:
        Extracted text content
    """
    try:
        from docx import Document
        
        logger.info(f"Extracting text from DOCX: {file_path}")
        doc = Document(file_path)
        
        text_parts = []
        
        # Extract text from paragraphs
        for para in doc.paragraphs:
            if para.text and para.text.strip():
                text_parts.append(para.text)
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        
        full_text = '\n\n'.join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters from DOCX")
        
        return full_text
        
    except ImportError:
        logger.error("python-docx library not installed. Install with: pip install python-docx")
        return ""
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX {file_path}: {e}")
        return ""


def extract_text_from_document(file_path: str, url: str) -> Dict:
    """
    Extract text from a document (PDF or DOCX) and return structured data.
    
    Args:
        file_path: Path to the downloaded document
        url: Original URL of the document
        
    Returns:
        Dictionary with keys: title, url, canonical_url, raw_text, sections, word_count
        Compatible with content_extractor.extract() output format
    """
    try:
        # Determine file type from extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Extract text based on file type
        if file_ext == '.pdf':
            raw_text = extract_text_from_pdf(file_path)
        elif file_ext in ['.docx', '.doc']:
            raw_text = extract_text_from_docx(file_path)
        else:
            logger.warning(f"Unsupported document type: {file_ext}")
            return {
                "title": "",
                "url": url,
                "canonical_url": url,
                "meta_description": "",
                "sections": [],
                "raw_text": "",
                "word_count": 0,
                "error": f"Unsupported document type: {file_ext}"
            }
        
        # Generate title from filename or URL
        filename = os.path.basename(file_path)
        title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
        
        # Create simple sections (treat entire document as one section for now)
        sections = []
        if raw_text and raw_text.strip():
            sections.append({
                "block_type": "document",
                "content": raw_text,
                "header": title,
                "header_level": 1,
                "parent_headers": [],
                "word_count": len(raw_text.split())
            })
        
        word_count = len(raw_text.split()) if raw_text else 0
        
        return {
            "title": title,
            "url": url,
            "canonical_url": url,
            "meta_description": f"Document: {title}",
            "sections": sections,
            "raw_text": raw_text,
            "word_count": word_count
        }
        
    except Exception as e:
        logger.error(f"Error extracting text from document {file_path}: {e}")
        return {
            "title": "",
            "url": url,
            "canonical_url": url,
            "meta_description": "",
            "sections": [],
            "raw_text": "",
            "word_count": 0,
            "error": str(e)
        }


def is_document_url(url: str) -> bool:
    """
    Check if a URL points to a supported document type.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL appears to be a PDF or DOCX document
    """
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith('.pdf') or path.endswith('.docx') or path.endswith('.doc')
