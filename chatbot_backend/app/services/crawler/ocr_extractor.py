# app/services/crawler/ocr_extractor.py
"""
OCR Extractor Module
Extracts text from images using EasyOCR with caching and post-processing.
"""

import logging
import os
import hashlib
import json
import time
import requests
import re
import asyncio
from typing import Dict, Any, List, Optional, Union
from io import BytesIO
import concurrent.futures

try:
    from PIL import Image, ImageOps, ImageEnhance
    import numpy as np
    import easyocr
except ImportError:
    # Handle missing dependencies gracefully
    Image = None
    np = None
    easyocr = None

logger = logging.getLogger("ocr_extractor")

class OCRExtractor:
    """
    Handles OCR operations with caching, robustness, and post-processing.
    """
    
    def __init__(self, cache_dir: str = "./ocr_cache", use_gpu: bool = False):
        if easyocr is None:
            logger.warning("EasyOCR/Pillow not installed. OCR will be disabled.")
            self.reader = None
        else:
            try:
                logger.info(f"Initializing EasyOCR (GPU={use_gpu})... this may take a moment on first run.")
                self.reader = easyocr.Reader(['en'], gpu=use_gpu)
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self.reader = None

        self.cache_dir = cache_dir
        self.use_gpu = use_gpu
        self._ensure_cache_dir()
        
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
            except Exception as e:
                logger.warning(f"Could not create cache dir {self.cache_dir}: {e}")

    def _get_cache_path(self, image_url: str) -> str:
        """Generate a safe cache file path based on URL hash."""
        url_hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.json")

    def extract_text_from_image(self, image_url: str, context: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
        """
        Main entry point for extracting text.
        NOTE: This method is synchronous but should be run in an executor to avoid blocking.
        """
        start_time = time.time()
        
        if not self.reader:
            return self._error_result("OCR libraries not initialized")
            
        # 1. Check Cache
        cache_path = self._get_cache_path(image_url)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    
                # Check expiration (e.g., 30 days)
                file_time = os.path.getmtime(cache_path)
                if time.time() - file_time < 30 * 24 * 3600:
                    cached_data['cached'] = True
                    return cached_data
            except Exception as e:
                logger.warning(f"Cache read error for {image_url}: {e}")

        # 2. Download Image
        try:
            # Download with strict timeout
            response = requests.get(image_url, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Compatible; Bot/1.0)'
            })
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                return self._error_result(f"Invalid content type: {content_type}")
                
            image_bytes = response.content
            if len(image_bytes) > 5 * 1024 * 1024: # 5MB limit
                return self._error_result("Image too large (>5MB)")
                
        except Exception as e:
            return self._error_result(f"Download failed: {str(e)}")

        # 3. Process Image
        try:
            img = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB (remove alpha)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert('RGB')
                
            # Resize if too huge (limit to 1920px width)
            if img.width > 1920:
                ratio = 1920 / img.width
                new_size = (1920, int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to numpy for EasyOCR
            img_np = np.array(img)
            
        except Exception as e:
            return self._error_result(f"Image processing failed: {e}")

        # 4. Perform OCR
        try:
            # detail=1 returns bounding boxes, text, and confidence
            results = self.reader.readtext(img_np, detail=1)
        except Exception as e:
            return self._error_result(f"OCR execution failed: {e}")
            
        # 5. Post-process
        processed_data = self._process_ocr_results(results)
        processed_data['processing_time'] = time.time() - start_time
        processed_data['cached'] = False
        
        # 6. Save to cache
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f)
        except Exception as e:
            logger.warning(f"Failed to write cache for {image_url}: {e}")
            
        return processed_data

    def _process_ocr_results(self, raw_results: List) -> Dict[str, Any]:
        """Convert raw EasyOCR results into structured data."""
        valid_blocks = []
        full_text_parts = []
        
        total_conf = 0
        count = 0
        
        structured = {
            "person_name": None,
            "person_title": None,
            "other_text": []
        }
        
        for bbox, text, conf in raw_results:
            # Skip very low confidence
            if conf < 0.3:
                continue
                
            # Helper to sanitize text for JSON (bbox needs to be lists, not tuples/numpy)
            bbox_list = [list(map(float, point)) for point in bbox]
            
            block = {
                "text": text,
                "confidence": float(conf),
                "bbox": bbox_list
            }
            valid_blocks.append(block)
            
            # For extraction, we use the text directly
            clean_txt = text.strip()
            full_text_parts.append(clean_txt)
            
            total_conf += conf
            count += 1
            
            # Attempt to pattern match specific fields
            # Names: Capitalized words (2-3) often on their own line
            # We apply targeted cleanup ONLY to potential names/titles
            if not structured['person_name'] and self._is_likely_name(clean_txt):
                structured['person_name'] = self._clean_targeted_text(clean_txt)
            elif not structured['person_title'] and self._is_likely_title(clean_txt):
                structured['person_title'] = self._clean_targeted_text(clean_txt)
            else:
                structured['other_text'].append(clean_txt)

        overall_confidence = (total_conf / count) if count > 0 else 0.0
        
        return {
            "success": True,
            "text": "\n".join(full_text_parts),
            "structured": {
                "person_name": structured['person_name'],
                "person_title": structured['person_title'],
                "other_text": "\n".join(structured['other_text'])
            },
            "raw_results": valid_blocks, # Keep strictly for debugging if needed
            "confidence": overall_confidence,
            "error": None
        }
        
    def _is_likely_name(self, text: str) -> bool:
        """Check if text looks like a name (2-3 Capitalized Words)."""
        # Allow dots for initials e.g. "John D. Doe"
        # Must not contain numbers or special chars usually
        if len(text.split()) not in (2, 3):
            return False
        if not text.replace('.', '').replace(' ', '').isalpha():
             return False
        # Check capitalization (Title Case)
        return text[0].isupper() and all(w[0].isupper() for w in text.split() if w)

    def _is_likely_title(self, text: str) -> bool:
        """Check against common job titles."""
        titles = [
            'CEO', 'CTO', 'CFO', 'COO', 'President', 'Director', 'Manager', 
            'Head', 'Lead', 'Chief', 'Officer', 'Engineer', 'Developer', 
            'Associate', 'Vice', 'Chair'
        ]
        text_lower = text.lower()
        return any(t.lower() in text_lower for t in titles)

    def _clean_targeted_text(self, text: str) -> str:
        """
        Apply aggressive OCR fixes ONLY to identified names/titles.
        Fixes 0 -> O, 1 -> I, l -> I, etc.
        """
        # Basic cleanup
        text = text.strip()
        
        # Specific substitutions for common name/title corruptions
        # 0 -> O (Zero to O)
        if '0' in text:
            text = text.replace('0', 'O')
        
        # 1 -> I or l -> I (One/Lower L to I) - reckless for general text, okay for specific titles
        # Careful with this one. "Al" (name) vs "AI" (artificial intelligence)
        # Maybe skip l->I unless it's strictly inside a known uppercase only string?
        
        return text

    def _error_result(self, msg: str) -> Dict[str, Any]:
        return {
            "success": False,
            "text": "",
            "structured": {},
            "confidence": 0.0,
            "error": msg,
            "processing_time": 0
        }
