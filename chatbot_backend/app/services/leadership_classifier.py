
import json
import logging
import hashlib
import re
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import boto3
except ImportError:
    boto3 = None

from app.config import settings

logger = logging.getLogger("leadership_classifier")

class LeadershipClassifier:
    """
    Classifies whether a person/role represents organization-wide leadership.
    Uses LLM with strict gating and caching.
    """

    def __init__(self):
        # Cache: hash(name+title+url) -> result
        self._cache: Dict[str, Dict] = {}
        
        # LLM Settings
        self.aws_region = getattr(settings, "AWS_REGION", "us-east-1")
        self.aws_model = getattr(settings, "AWS_MODEL", "anthropic.claude-3-5-sonnet-20241022-v1:0")
        self._bedrock_client = None
        
        # Explicit leadership keywords for gating
        self.leadership_keywords = [
            "ceo", "chief", "president", "founder", "chairman", "director", 
            "head", "lead", "vp", "vice president", "principal", "partner",
            "manager", "executive", "board", "c-suite"
        ]

    def _get_bedrock_client(self):
        """Lazily initialize AWS Bedrock client."""
        if not self._bedrock_client:
            if boto3 is None:
                logger.error("boto3 not installed, cannot use Bedrock")
                return None
                
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.aws_region,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
            else:
                self._bedrock_client = boto3.client("bedrock-runtime", region_name=self.aws_region)
        return self._bedrock_client

    def classify_leadership_role(self, input_data: Dict) -> Dict:
        """
        Determine if the role represents organization-wide leadership.
        
        Input fields:
        {
          "person_name": str,
          "person_title": str,
          "page_type": str,   # profile, job_posting, news, marketing
          "source_url": str,
          "text_snippet": str, # 1-3 lines
          "chunk_count": int   # Number of chunks this person appears in (optional)
        }
        
        Returns:
        {
          "is_leadership": bool,
          "confidence": float,
          "reason": str
        }
        """
        person_name = input_data.get("person_name") or ""
        person_title = input_data.get("person_title") or ""
        page_type = input_data.get("page_type")
        source_url = input_data.get("source_url") or ""
        chunk_count = input_data.get("chunk_count", 0)
        
        # 0. Check Cache
        cache_key = self._generate_cache_key(person_name, person_title, source_url)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. Gating Logic (Fail Fast)
        # Call LLM only if:
        # - Title contains leadership keyword OR
        # - Page type != job_posting OR
        # - Person appears in multiple chunks (sign of importance)
        
        title_lower = person_title.lower()
        has_keyword = any(kw in title_lower for kw in self.leadership_keywords)
        is_job_posting = page_type == "job_posting"
        is_frequent = chunk_count >= 2
        
        should_call_llm = has_keyword or (not is_job_posting) or is_frequent
        
        if not should_call_llm:
            result = {
                "is_leadership": False,
                "confidence": 0.0,
                "reason": "Gated: No leadership keywords and not a profile/frequent entity."
            }
            self._cache[cache_key] = result
            return result

        # 2. Prepare LLM Prompt
        prompt = f"""
You are a strict corporate hierarchy classifier.
Analyze if this person holds an ORGANIZATION-WIDE LEADERSHIP role.

Name: {person_name}
Title: {person_title}
Context: {input_data.get('text_snippet', '')}
Page Type: {page_type}

RULES:
- "Leadership" means company-level authority, strategy, or C-suite/VP/Director level.
- Managers, HR Specialists, Consultants, Engineers are NOT leadership.
- Project managers, Regional leads (unless huge region) are usually NOT organization-wide leadership.
- Associate Directors are lower confidence than Directors.
- Job postings are NEVER leadership roles (they are open slots).
- Testimonials are NOT leadership roles.

Return JSON ONLY:
{{
  "is_leadership": true | false,
  "confidence": float (0.0 to 1.0),
  "reason": "short explanation"
}}
"""

        # 3. Call LLM
        try:
            response = self._invoke_llm(prompt)
            data = json.loads(response)
            
            # 4. Apply Bounds & Safety
            confidence = float(data.get("confidence", 0.0))
            
            # Clip confidence [0.2, 1.2] (User Refinement 2)
            # We allow 1.2 to support potential boosting logic downstream, 
            # though locally we might cap at 1.0 for valid probabilities.
            # The requirement was: leadership_confidence = min(max(confidence, 0.2), 1.2)
            # Wait, 1.2 implies boosting beyond raw probability. 
            # I will store the clipped value.
            
            clipped_conf = min(max(confidence, 0.2), 1.2)
            
            # Hard override for Associate/Assistant (common false positives)
            if "associate" in title_lower or "assistant" in title_lower:
                 if clipped_conf > 0.5:
                     clipped_conf = 0.5
                     data["is_leadership"] = False
                     data["reason"] += " (Demoted: Associate/Assistant role)"

            result = {
                "is_leadership": data.get("is_leadership", False),
                "confidence": clipped_conf,
                "reason": data.get("reason", "LLM decision")
            }
            
            self._cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"LLM Classification failed: {e}")
            # Fail safe
            return {
                "is_leadership": False,
                "confidence": 0.0,
                "reason": f"Error: {str(e)}"
            }

    def classify_page_type(self, url: str, text_snippet: str) -> Dict:
        """
        Classify page type using LLM (Lightweight).
        Types: leadership_profile, employee_profile, job_posting, news_article, marketing_page
        """
        cache_key = hashlib.md5(f"page_type:{url}".encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = f"""
Classify this webpage based on URL and text.
URL: {url}
Text: {text_snippet[:500]}

Categories:
- leadership_profile (Bio of a specific leader/executive)
- employee_profile (Bio of a regular staff member)
- job_posting (Careers, open positions)
- news_article (Press release, blog, update)
- marketing_page (Product, homepage, general info)

Return JSON ONLY:
{{
  "type": "category_name",
  "confidence": float
}}
"""
        try:
            response = self._invoke_llm(prompt)
            data = json.loads(response)
            result = {
                "type": data.get("type", "marketing_page"),
                "confidence": float(data.get("confidence", 0.0))
            }
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Page classification failed: {e}")
            return {"type": "general", "confidence": 0.0}

    def validate_title(self, title: str, context: str) -> bool:
        """
        Validate if a title is explicit vs inferred.
        Fail-closed: Returns False on error/ambiguity.
        """
        if not title: return False
        
        # Cache (title + brief context hash)
        ctx_hash = hashlib.md5(context[:100].encode()).hexdigest()
        cache_key = hashlib.md5(f"title_val:{title}:{ctx_hash}".encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = f"""
Is this a VALID professional title explicitly stated in the text?
Or is it inferred/constructed?

Title: "{title}"
Context: "...{context}..."

Rules:
- "Asia Managing Director" if text says "Managing Director for Asia" is VALID.
- "Project Lead" if text implies he leads a project but doesn't state the title is INVALID (Inferred).
- "Team Member" is INVALID (Generic).
- "Manager" is VALID.

Return JSON ONLY:
{{
  "valid_title": true | false
}}
"""
        try:
            response = self._invoke_llm(prompt)
            data = json.loads(response)
            is_valid = data.get("valid_title", False)
            self._cache[cache_key] = is_valid
            return is_valid
        except Exception as e:
            logger.error(f"Title validation failed: {e}")
            return False # Fail-closed

    def _invoke_llm(self, prompt: str) -> str:
        """Invoke Claude via Bedrock."""
        client = self._get_bedrock_client()
        if not client:
            raise Exception("Bedrock client unavailable")
            
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 150,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        })
        
        response = client.invoke_model(
            modelId=self.aws_model,
            body=body
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']

    def _generate_cache_key(self, name: str, title: str, url: str) -> str:
        raw = f"{name}:{title}:{url}"
        return hashlib.md5(raw.encode()).hexdigest()

# Singleton instance
leadership_classifier = LeadershipClassifier()
