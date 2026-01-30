from typing import List, Dict, Optional, Tuple, Union, Set, Any
import difflib
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
from app.utils.text import normalize_text

# Initialize logger
logger = logging.getLogger("rag")
logging.basicConfig(level=logging.INFO)

# RAG limits to prevent overloading LLM context
MAX_QUERY_EXPANSIONS = 8   # Maximum queries (original + expansions)
# MAX_CONTEXT_TOKENS now configurable via settings.MAX_CONTEXT_TOKENS (default: 4000)
def _get_max_context_tokens():
    """Get max context tokens from settings."""
    return getattr(settings, "MAX_CONTEXT_TOKENS", 4000)
# MIN_SCORE is now configurable via settings.RAG_MIN_SCORE (default: 0.35)

# Conversation summarization settings
MAX_VERBATIM_MESSAGES = 20   # Keep last 10 Q&A pairs (20 messages) verbatim
SUMMARY_TRIGGER_THRESHOLD = 20  # Start summarizing when history exceeds this count


# ============================================
# CONSTANTS & ENUMS
# ============================================

class AnswerMode:
    FULL = "FULL"
    PARTIAL_TRANSPARENT = "PARTIAL_TRANSPARENT"
    FOLLOWUP = "FOLLOWUP"
    NO_DATA_CONFIRMED = "NO_DATA_CONFIRMED"

# ============================================
# RAG SEARCH HELPERS
# ============================================


def _estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars per token for English)."""
    return len(text) // 4 if text else 0


# ============================================
# ORG & LEADERSHIP HELPERS (FIX 1, 3, 6)
# ============================================

# RAG Answer Selection: thresholds (leadership data often has lower per-chunk scores)
LEADERSHIP_MIN_SCORE = 0.15
GENERAL_MIN_SCORE = 0.20

ALLOWED_LEADERSHIP_TITLES = {
    "director",
    "managing director",
    "associate director",
    "board member",
    "founder",
    "co-founder",
    "ceo",
    "cto",
    "cfo",
    "coo",
    "president",
    "vice president",
    "vp",
    "chairman",
    "head",
    "head of",
    "chief",
    "exec",
}

# Canonical list for fuzzy title matching (subset + variants)
LEADERSHIP_TITLE_KEYWORDS = [
    "director", "chairman", "ceo", "cfo", "cto", "coo",
    "associate director", "vice president", "vp", "president",
    "chief", "head of", "founder", "managing director",
]


def normalize_title(title: Optional[str]) -> str:
    """Normalize title for leadership check: en/em-dash to hyphen, & to 'and', lowercased."""
    if not title:
        return ""
    return (
        title.lower()
        .replace("\u2013", "-")   # en-dash
        .replace("\u2014", "-")   # em-dash
        .replace("&", " and ")
    )


def is_leadership_role(title: Optional[str]) -> bool:
    """Check if title indicates leadership role using fuzzy/semantic matching."""
    if not title or not isinstance(title, str):
        return False
    title = normalize_title(title)
    return any(role in title for role in LEADERSHIP_TITLE_KEYWORDS)


# Career/job page blocker (first line of defense)
CAREER_KEYWORDS = (
    "job", "career", "we are looking", "about the role",
    "responsibilities", "requirements", "preferred skills",
    "key skills", "apply", "opening", "vacancy", "position",
    "role description",
)


def is_career_chunk(chunk: Dict) -> bool:
    """True if chunk looks like a job/career page (job descriptions, role headers, etc.)."""
    payload = chunk.get("payload", {})
    text = (chunk.get("text") or payload.get("text") or "").lower()
    file_name = (chunk.get("file_name") or payload.get("file_name") or payload.get("page_title") or "").lower()
    return any(k in text or k in file_name for k in CAREER_KEYWORDS)


JOB_POSTING_PHRASES = [
    "we are hiring",
    "job description",
    "responsibilities",
    "requirements",
    "apply now",
    "experience required",
]


def looks_like_job_posting(text: Optional[str]) -> bool:
    """True if the text content looks like a specific job advertisement."""
    if not text:
        return False
    t = text.lower()
    return any(p in t for p in JOB_POSTING_PHRASES)


# Person-name validation (reject section headers, page titles, role-only labels)
NON_PERSON_PREFIXES = (
    "about", "brief", "getting", "meet", "our", "the",
    "skip", "log in", "accessibility", "understanding",
    "key skills", "preferred skills", "role description",
)


def is_probable_person_name(name: str) -> bool:
    """Reject obvious non-person labels (section headers, page titles)."""
    if not name:
        return False
    name = name.strip()
    lname = name.lower()
    if lname.startswith(NON_PERSON_PREFIXES):
        return False
    if len(name.split()) > 5:
        return False
    tokens = name.split()
    capitalized = sum(1 for t in tokens if t[:1].isupper())
    if capitalized < 2:
        return False
    return True


def is_role_only_name(name: str) -> bool:
    """Reject names that are just a role title with no person (e.g. 'Associate Director')."""
    if not name:
        return False
    lname = name.lower()
    return any(
        lname == k or lname.startswith(k + " ")
        for k in (
            "director", "associate director", "manager",
            "vp", "vice president", "head", "lead",
        )
    )


def extract_leadership_entities(
    chunks: List[Dict],
    target_org: Optional[str] = None,
    query_type: Optional[str] = None,
) -> List[Dict]:
    """Extract verified leadership entities (name, title) from retrieved chunks.
    Leadership queries are org-soft: org filtering is skipped when query_type == 'leadership_list'.
    """
    seen_names: Set[str] = set()
    entities: List[Dict] = []
    for c in chunks:
        payload = c.get("payload", {})
        name = (payload.get("person_name") or "").strip()
        title = (payload.get("person_title") or "").strip()
        text = (c.get("text") or payload.get("text") or "").strip()
        
        # FIX 2: Correct logic for career pages vs leadership profiles
        # Career page + leadership title -> KEEP
        # Career page + job posting phrases -> DROP
        if is_career_chunk(c):
            if looks_like_job_posting(text) and not is_leadership_role(title):
                 logger.debug("[LEADERSHIP DROP] job posting: %s", name)
                 continue
            if not is_leadership_role(title):
                 logger.debug("[LEADERSHIP DROP] career chunk without leadership: %s", name)
                 continue

        if not name or name == "Unknown":
            continue
        if not is_leadership_role(title):
            logger.debug("[LEADERSHIP DROP] not leadership role: %s | %s", name, title)
            continue
        if not is_probable_person_name(name):
            logger.debug("[LEADERSHIP DROP] not person name: %s", name)
            continue
        if is_role_only_name(name):
            continue
        # Leadership extraction must NOT depend on organization metadata (org-soft).
        # Only person name + leadership role + non-career chunk matter.
        key = normalize_text(name)
        if key in seen_names:
            continue
        seen_names.add(key)
        entities.append({"name": name, "title": title})
    return entities


def format_entities(entities: List[Dict]) -> str:
    """Format list of entities as 'Name (Title), Name (Title), and Name (Title)'."""
    if not entities:
        return ""
    if len(entities) == 1:
        return f"{entities[0]['name']} ({entities[0]['title']})"
    if len(entities) == 2:
        return f"{entities[0]['name']} ({entities[0]['title']}) and {entities[1]['name']} ({entities[1]['title']})"
    parts = [f"{e['name']} ({e['title']})" for e in entities[:-1]]
    return ", ".join(parts) + f", and {entities[-1]['name']} ({entities[-1]['title']})"


def infer_org_from_chunks(chunks: List[Dict]) -> Optional[str]:
    """Cheap fallback: infer org name from chunk text/filenames (e.g. Polus in content or 'Polus Solutions | ...')."""
    for c in chunks:
        payload = c.get("payload", {})
        text = (c.get("text") or payload.get("text") or "").strip()
        file_name = (c.get("file_name") or payload.get("file_name") or payload.get("page_title") or "").strip()
        combined = f"{text} {file_name}"
        if "Polus Solutions" in combined:
            return "Polus Solutions"
        if "Polus" in combined:
            return "Polus"
    return None


def generate_leadership_response(
    entities: List[Dict],
    top_score: float,
    org_name: str = "the organization",
) -> str:
    """Generate response with appropriate confidence language."""
    if not entities:
        return f"I don't have sufficient information about {org_name} leadership in the knowledge base."
    formatted = format_entities(entities)
    if top_score >= 0.25:
        return f"{org_name} leadership includes {formatted}."
    if top_score >= LEADERSHIP_MIN_SCORE:
        return (
            f"Based on available information, {org_name} leadership includes {formatted}. "
            "This may not be a complete list."
        )
    return f"I don't have sufficient information about {org_name} leadership in the knowledge base."


def mentions_org(chunk: Dict, target_org: str) -> bool:
    """
    FIX 1 & 3: Strong mentions_org() detector.
    Returns True if the chunk is explicitly about the target_org.
    """
    payload = chunk.get("payload", {})
    
    # 1. Check Explicit Organization Field (Best Source)
    chunk_org = payload.get("organization")
    if chunk_org:
        # Normalize and compare
        if normalize_text(chunk_org) == normalize_text(target_org):
            return True
        # If explicitly set to something else, then False
        return False
        
    # 2. Fallback: Context/Text (Only if organization field is missing)
    # This shouldn't happen often if Fix 1/2 works, but good for safety.
    text = (payload.get("text") or "").lower()
    t_org = target_org.lower()
    
    # Check domain/url/source
    domain = payload.get("domain", "")
    url = payload.get("url", "")
    source = payload.get("source", "")
    
    if t_org in domain: return True
    if f"/{t_org}" in url: return True
    if source in {f"{t_org}_site", f"{t_org}_pdf"}: return True
    
    return False



# ============================================
# PROMPT INSTRUCTIONS (FIX 17 & 22)
# ============================================

CLASSIFICATION_INSTRUCTION = """
[SYSTEM: CLASSIFICATION]
After your answer, you MUST classify it by appending a JSON object on a new line. 
Format: {"answer_mode": "FULL" | "PARTIAL_TRANSPARENT" | "NoData", "is_generic": boolean}
- FULL: You found specific information in the context to answer the user's question.
- PARTIAL_TRANSPARENT: You found some related info but not the exact answer (e.g. wrong domain/person).
- NoData: The context does not contain relevant information.
- is_generic: true if you are giving a general refusal or small talk, false if using context.
Example:
{"answer_mode": "FULL", "is_generic": false}
"""

def format_general_context(chunks: List[Dict]) -> str:
    """Format chunks for general Q&A."""
    context = ""
    for i, chunk in enumerate(chunks, 1):
        payload = chunk.get("payload", {})
        text = payload.get("text", "").strip()
        source = chunk.get("file_name", "Unknown Source")
        
        context += f"Source {i} ({source}):\n{text}\n\n"
    return context

def format_person_context(chunks: List[Dict], person_detection: Dict) -> str:
    """Format chunks specifically for person queries."""
    context = f"Intent: Find details about {person_detection.get('person_name', 'a person')}\n\n"
    
    # Group by chunk type
    profiles = []
    others = []
    
    for chunk in chunks:
        payload = chunk.get("payload", {})
        if payload.get("chunk_type") == "person_profile":
            profiles.append(chunk)
        else:
            others.append(chunk)
            
    if profiles:
        context += "=== PRIMARY PROFILES ===\n"
        for p in profiles:
            payload = p.get("payload", {})
            name = payload.get("person_name", "Unknown")
            title = payload.get("person_title", "Unknown Role")
            org = payload.get("organization", "Polus Solutions")
            text = payload.get("text", "")
            context += f"Name: {name}\nTitle: {title}\nOrg: {org}\nDetails: {text}\n\n"
            
    if others:
        context += "=== RELATED MENTIONS ===\n"
        for o in others:
            text = o.get("payload", {}).get("text", "")
            context += f"{text}\n\n"
            
    return context


# ============================================
# QUERY ANALYSIS & RAG HELPERS
# ============================================

def classify_query(normalized_query: str) -> Dict[str, str]:
    """
    Classify the query type to optimize retrieval strategy.
    Lightweight, fast detection (<10ms).
    """
    if not normalized_query:
        return {"query_type": "exploratory", "complexity": "medium"}
        
    query_lower = normalized_query
    
    # 0. Leadership List (New Priority)
    # Detection rule: plural language + leadership role + org presence (implied by context usually)
    list_patterns = [r"who all", r"list ", r"members", r"who are the", r"staff", r"team", r"everyone"]
    role_patterns = [r"director", r"vp", r"head", r"leadership", r"management", r"executives", r"board"]
    
    # Check for plural/list intent + leadership role
    has_list_intent = any(re.search(p, query_lower) for p in list_patterns)
    has_leadership_role = any(re.search(p, query_lower) for p in role_patterns)
    
    if has_list_intent and has_leadership_role:
        # Negative guard: Avoid misclassifying singular person queries like "Who is the director of Polus Solutions?"
        # Simple heuristic: "who is the [role]" or "who is [name]" (without "all" or "list")
        is_singular_role_query = re.search(r"who is the (?:director|vp|head|ceo|cto)", query_lower)
        is_singular_name_query = re.search(r"who is (?!the )", query_lower) and len(query_lower.split()) <= 5
        
        if not (is_singular_role_query or is_singular_name_query):
            return {"query_type": "leadership_list", "complexity": "medium"}

    # 1. Person queries (Highest Priority)
    person_patterns = [
        r"who is", r"who's", r"tell me about", r"what does .* do", 
        r"who are", r"contact", r"email", r"reach"
    ]
    if any(re.search(p, query_lower) for p in person_patterns):
        return {"query_type": "person", "complexity": "medium"}

    # 2. Factual queries
    factual_patterns = [
        r"what is", r"define", r"when was", r"where is", 
        r"what does .* mean"
    ]
    if any(re.search(p, query_lower) for p in factual_patterns):
        return {"query_type": "factual", "complexity": "simple"}

    # 3. Procedural/How-to
    procedural_starts = ("how to", "how do i", "steps to", "guide to", "tutorial")
    if query_lower.startswith(procedural_starts) or "how do i" in query_lower:
        return {"query_type": "procedural", "complexity": "medium"}

    # 4. Troubleshooting
    trouble_words = {"why", "error", "not working", "problem", "issue", "failed", "crash", "bug"}
    if any(w in query_lower for w in trouble_words):
        return {"query_type": "troubleshooting", "complexity": "medium"}

    # 5. Comparison
    compare_patterns = [r" vs ", r" versus ", r"difference between", r"compare", r"better than"]
    if any(re.search(p, query_lower) for p in compare_patterns):
        return {"query_type": "comparison", "complexity": "complex"}

    # 5. History / Background (For P1 Domain Mismatch Logic)
    history_patterns = [r"history", r"founding", r"legacy", r"timeline", r"when did .* start", r"background", r"story of"]
    if any(re.search(p, query_lower) for p in history_patterns):
        return {"query_type": "history", "complexity": "medium"}

    return {"query_type": "exploratory", "complexity": "medium"}


def detect_person_query(normalized_query: str, prior_context: Optional[Dict] = None, known_people: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Detect if query is asking about a person and extract details.
    Operates on NORMALIZED TEXT ONLY.
    
    Args:
        normalized_query: lowercased, stripped query string
        prior_context: Optional Dict containing 'person_name' and 'role_title' from history
        known_people: Optional List of known person names for fuzzy correction
    """
    result = {
        "is_person_query": False,
        "query_type": None,
        "person_name": None,
        "role_title": None,
        "intent": "general"
    }
    
    # 0. Check for continuation/pronoun usage if context exists
    if prior_context and prior_context.get("person_name"):
        # Check for vague referral keywords
        pronouns = ["he", "she", "him", "her", "his", "hers", "they", "them", "this person", "the person"]
        continuations = ["tell me more", "what else", "details", "background", "experience", "education", "contact", "email", "phone", "yes", "yeah", "correct"]
        
        query_words = normalized_query.split()
        
        # If query is very short (< 5 words) OR contains pronouns/continuation words
        is_short = len(query_words) < 5
        has_pronoun = any(p in query_words for p in pronouns)
        is_continuation = any(c in normalized_query for c in continuations)
        
        if is_short or has_pronoun or is_continuation:
            # Inherit context!
            result["is_person_query"] = True
            result["person_name"] = prior_context["person_name"]
            result["role_title"] = prior_context.get("role_title")
            result["intent"] = "continuation"
            result["query_type"] = "attribute_lookup" if has_pronoun else "general_continuation"
            
            # If the user asks specifically about an attribute, we should note that, 
            # but for now, just anchoring the person is the critical fix.
            return result

    query_lower = normalized_query
    
    # 0. FIX 2: Disable person-name logic for leadership_list
    # If the query was already classified as leadership_list, we skip name extraction
    # This prevents "Brief Description" and footer junk from being detected as names
    if prior_context and prior_context.get("query_type") == "leadership_list":
        result.update({
             "is_person_query": True,
             "query_type": "leadership_list",
             "person_name": None,
             "role_title": "director", # Default expected role for retrieval
             "intent": "team"
        })
        return result

    # 1. Detect Intent
    if any(w in query_lower for w in ["contact", "email", "reach", "phone"]):
        result["intent"] = "contact"
    elif any(w in query_lower for w in ["do", "role", "responsibilities", "function"]):
        result["intent"] = "role"
    elif any(w in query_lower for w in ["team", "people", "members", "staff", "leadership", "management", "founders", "executives", "directors"]):
        result["intent"] = "team"
    elif any(w in query_lower for w in ["about", "bio", "background", "history"]):
        result["intent"] = "bio"
        
    # --- FIX 3: ROLE LOOKUP DETECTION ---
    # Explicitly check for role terms BEFORE person extraction to prevent "HR" being treated as a name
    role_terms = {"hr", "human resources", "finance", "admin", "it", "support", "legal", "marketing", "operations", "sales"}
    
    # Check if query contains role terms (whole word match)
    has_role_term = False
    found_role = None
    for term in role_terms:
         if re.search(r'\b' + re.escape(term) + r'\b', query_lower):
             has_role_term = True
             found_role = term
             break
             
    if has_role_term:
        # If it's a "who is the [role]" query
        if "who" in query_lower or "contact" in query_lower:
            result["is_person_query"] = True
            result["query_type"] = "role_lookup"
            result["intent"] = "role_lookup"
            result["role_title"] = found_role
            # We explicitly do NOT set person_name to avoid name-based search confusion
            return result

    # 2. Check for Team List
    if result["intent"] == "team" or any(phrase in query_lower for phrase in ["show me the team", "who is the leadership", "who runs the company"]):
        result["is_person_query"] = True
        result["query_type"] = "team_list"
        return result

    # 3. Extract Role Title
    titles = [
        "ceo", "cto", "cfo", "director", "manager", "vp", "president", "chairman",
        "chief executive officer", "vice president", "head of", "lead", "founder", "co-founder", "managing director"
    ]
    for title in titles:
        if f"the {title}" in query_lower or f"{title} of" in query_lower:
            result["role_title"] = title
            result["is_person_query"] = True
            result["query_type"] = "role_based"
            break
            
    # 4. Extract Person Name (Pattern Based for Normalized Text)
    # Using explicit patterns since we cannot rely on capitalization
    
    # Patterns to capture name: "who is [name]", "email [name]", "contact [name]"
    # We look for the part matching the name
    name_patterns = [
        r"who is ([\w\s]+)(?:\?|$)",
        r"who's ([\w\s]+)(?:\?|$)",
        r"tell me about ([\w\s]+)(?:\?|$)",
        r"contact ([\w\s]+)(?:\?|$)",
        r"email ([\w\s]+)(?:\?|$)",
        r"reach ([\w\s]+)(?:\?|$)",
        r"role of ([\w\s]+)(?:\?|$)",
        r"what does ([\w\s]+) do(?:\?|$)"
    ]
    
    potential_name = None
    
    for pattern in name_patterns:
        match = re.search(pattern, query_lower)
        if match:
            extracted = match.group(1).strip()
            
            # --- FIX: Strip context phrases (e.g. "at Polus Solutions") ---
            # This ensures "Ramya A at Polus Solutions" -> "Ramya A"
            context_stops = [r"\s+at\s+.*", r"\s+from\s+.*", r"\s+in\s+.*", r"\s+who\s+.*"]
            for stop in context_stops:
                extracted = re.sub(stop, "", extracted).strip()
                
            # Heuristic: Valid names are usually 1-3 words
            if 1 <= len(extracted.split()) <= 3:
                potential_name = extracted
                break
    
    # If no pattern matched, but we have a title match context like "is [name] the ceo?"
    if not potential_name and result["role_title"]:
         # Try to extract name before "the [title]"
         # e.g. "is john doe the ceo"
         match = re.search(f"is ([\w\s]+) the {result['role_title']}", query_lower)
         if match:
             potential_name = match.group(1).strip()

    if potential_name:
        # cleanup validation
        stop_words = {"the", "a", "an", "is", "of", "in", "at", "for", "to"}
        if potential_name not in stop_words:
            result["person_name"] = potential_name
            result["is_person_query"] = True
            result["query_type"] = "specific_person"

            # Fuzzy name correction
            if known_people:
                best_match = None
                best_score = 0.0
                potential_lower = potential_name.lower()
                
                # 1. Substring Match (e.g. "Anjana" -> "Anjana Palat")
                for person in known_people:
                    if not person: continue
                    p_lower = person.lower()
                    
                    # If specific name is in full name (and reasonable length)
                    if len(potential_lower) > 3 and potential_lower in p_lower:
                        # Prefer full word match if possible
                        if re.search(r'\b' + re.escape(potential_lower) + r'\b', p_lower):
                            best_match = person
                            best_score = 1.0 # Perfect part-match
                            break
                
                # 2. Fuzzy Match (if no perfect substring)
                if best_score < 0.9: 
                    for person in known_people:
                        if not person: continue
                        score = fuzzy_match(potential_name, person)
                        if score > best_score:
                            best_score = score
                            best_match = person
                
                # Threshold for correction (0.75 covers Remya->Ramya at 0.8)
                if best_score > 0.75: 
                     result["person_name"] = best_match
                     result["original_name"] = potential_name
                     result["fuzzy_confidence"] = best_score

    return result


def normalize_person_name(name: str) -> str:
    """
    Strict normalization for person names:
    - Lowercase
    - Remove punctuation
    - Remove consecutive duplicate letters
    - Remove single-letter initials
    """
    if not name:
        return ""
    n = name.lower().strip()
    # Remove punctuation except spaces
    n = re.sub(r'[^\w\s]', '', n)
    # Remove repeated characters
    n = re.sub(r'(.)\1+', r'\1', n)
    # Remove single-letter initials
    n = re.sub(r'\b[a-z]\b', '', n)
    # Collapse multiple spaces
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def fuzzy_match(s1: str, s2: str) -> float:
    """
    Return a similarity score [0-1] between two strings using difflib.
    Handles typos in names/titles.
    Uses normalized inputs.
    """
    if not s1 or not s2:
        return 0.0
    # Use person-specific normalization for better name/title matching
    s1_norm = normalize_person_name(s1)
    s2_norm = normalize_person_name(s2)
    
    # Rapidfuzz is much better/faster if available
    if RAPIDFUZZ_AVAILABLE:
        return fuzz.token_sort_ratio(s1_norm, s2_norm) / 100.0
        
    return difflib.SequenceMatcher(None, s1_norm, s2_norm).ratio()


def get_keyword_score(text: str, query: str) -> float:
    """
    Simple keyword overlap score (Jaccard-lite).
    Returns score based on number of query terms found in text.
    """
    if not text or not query:
        return 0.0
        
    text_lower = text.lower()
    query_lower = query.lower()
    
    # Tokenize and remove short/common words
    stop_words = {"this", "that", "with", "from", "your", "mine", "about", "what", "where", "who", "whom"}
    query_terms = [
        w.strip("?.,!") 
        for w in query_lower.split() 
        if len(w) > 2 and w not in stop_words
    ]
    
    if not query_terms:
        return 0.0
        
    matches = sum(1 for term in query_terms if term in text_lower)
    return matches / len(query_terms)


def build_retrieval_filters(
    collection_id: Optional[str],
    query_classification: Dict,
    person_detection: Dict,
    soft: bool = True
) -> Dict:
    """
    Build Qdrant filter conditions. 
    If soft=True, we avoid hard exclusions for person queries to allow fallback.
    """
    
    filters = {"must": []}
    
    if collection_id:
        filters["must"].append({"key": "collection_id", "match": {"value": collection_id}})
    
    # Filter 1: Quality Baseline (Moved to sorting/boosting only)
    # Removing hard filter to ensure backward compatibility with older chunks
    # filters["must"].append({
    #    "key": "content_quality_score",
    #    "range": {"gte": 0.3}
    # })
    
    should_conditions = []
    
    # Filter 2: Person Query Handling (Moved to Python reranker for search stability)
    # Filter 3: Procedural Boost (Moved to Python reranker)
    # Filter 4: Canonical Preference (Moved to Python reranker)
    
    if should_conditions:
        filters["should"] = should_conditions
        
    return filters


# FIX 18: Source Priority Rules
SOURCE_PRIORITY = {
    "about_us": 1.0,
    "team_page": 1.0,
    "leadership_page": 0.9,
    "press_release": 0.7,
    "job_posting": 0.3,
    # Fallbacks
    "general": 0.5,
    "blog": 0.5
}

def rerank_results(
    results: List,
    query: str,
    query_classification: Dict,
    person_detection: Dict,
    embeddings_model=None, # FIX 16: Passed for embedding similarity
    **kwargs
) -> List:
    """
    Rerank search results with diversity, quality, and relevance boosting.
    Enhanced with Fix 2, 4, 5, 6, 7, 8 (Org-Aware Logic) + Fix 16, 18.
    """
    query_lower = query.lower()
    reranked = []
    
    # Diversity tracking
    seen_urls = {}       # url -> count
    seen_people = {}     # person_name -> count
    primary_person_found = False
    
    # Check if query mentions an external organization
    # (Simple heuristic: look for "at [Org]", "of [Org]", or "from [Org]")
    org_mentions = re.findall(r'(?:at|of|from|with) ([\w\s]+)', query_lower)
    has_external_org = len(org_mentions) > 0
    
    # Metadata for fuzzy matching suggestions
    fuzzy_matches = [] # List of (name, title, score)
    
    # FIX 3: Enforce org-scope hard filter in leadership scoring
    query_org = kwargs.get("query_org")
    is_leadership_list = query_classification.get("query_type") == "leadership_list"
    is_role_lookup = query_classification.get("query_type") == "role_lookup" # FIX 16
    
    if is_leadership_list and query_org:
        filtered_results = []
        for res in results:
            meta = res.get("payload", {})
            # FIX: REMOVED org filter for leadership. Org is for display only.
            
            # Refinement 3: Strict domain allow-list for leadership_list
            allowed_domains = {"people", "about", "leadership"}
            chunk_domain = meta.get("domain")
            if chunk_domain and chunk_domain not in allowed_domains:
                logger.info(f"[RAG FILTER] Dropped chunk due to domain restriction: {chunk_domain}")
                continue
                
            filtered_results.append(res)
        results = filtered_results

    # FIX 1 & 8: Extract locked state
    rag_state = kwargs.get("rag_state", {})
    target_org = rag_state.get("target_org", "polus")
    
    # Pre-calculate person counts for gating logic
    person_counts = {}
    for result in results:
        meta = result.get("payload", {})
        p_name = meta.get("person_name")
        if p_name:
             person_counts[p_name] = person_counts.get(p_name, 0) + 1

    # Check existence
    query_name = person_detection.get("person_name")
    person_detected = False
    if query_name:
        query_name_norm = normalize_text(query_name)
        for result in results:
            meta = result.get("payload", {})
            p_name = meta.get("person_name")
            if p_name and query_name_norm in normalize_text(p_name):
                person_detected = True
                break
    
    
    leadership_detected = False
    
    person_presence = {
        "found": person_detected,
        "has_title": False,
        "has_leadership_keyword": False,
        "source_domains": []
    }
    
    # FIX 16: Pre-compute Role Embedding if needed
    query_role_embedding = None
    if is_role_lookup and embeddings_model:
        role_title = person_detection.get("role_title")
        if role_title:
             try:
                 query_role_embedding = embeddings_model.encode(role_title)
             except Exception as e:
                 logger.error(f"Failed to embed role title: {e}")

    for result in results:
        base_score = result.get("score", 0)
        boost = 1.0
        metadata = result.get("payload", {})
        
        name = metadata.get("person_name", "Unknown")
        title = metadata.get("person_title", "")
        
        # Populate person_presence
        if person_detection.get("is_person_query"):
            domain = metadata.get("domain", "general")
            if domain not in person_presence["source_domains"]:
                person_presence["source_domains"].append(domain)
            if title:
                person_presence["has_title"] = True
            if leadership_detected: 
                pass
        
        # --- FIX 18: Source Priority Rules ---
        source_type = metadata.get("page_type") or metadata.get("source_type", "general") # page_type from crawler is best
        # normalized logic
        priority_boost = 0.5 # Default low
        if "about" in source_type or "about_us" in source_type: priority_boost = SOURCE_PRIORITY["about_us"]
        elif "team" in source_type: priority_boost = SOURCE_PRIORITY["team_page"]
        elif "leadership" in source_type: priority_boost = SOURCE_PRIORITY["leadership_page"]
        elif "press" in source_type or "news" in source_type: priority_boost = SOURCE_PRIORITY["press_release"]
        elif "job" in source_type or "career" in source_type: priority_boost = SOURCE_PRIORITY["job_posting"]
        else: priority_boost = 0.8 # Standard content
        
        boost *= priority_boost
        
        # --- FIX 4: Redefine External Org Logic ---
        detected_org = metadata.get("organization")
        
        is_internal = False
        is_external = False
        
        if detected_org and normalize_text(detected_org) == normalize_text(target_org):
            is_internal = True
            is_external = False
        elif detected_org is None:
            # FIX 4: Unknown != External
            is_internal = False
            is_external = False
        else:
            # Different organization -> External
            is_internal = False
            is_external = True
            
        # FIX 10: Debug Logging (Temporary)
        if rag_state.get("intent") == "leadership_list":
            logger.info(
                "[ORG DEBUG] name=%s | title=%s | organization=%s | external=%s",
                name, title, 
                detected_org, 
                is_external
            )

        # --- FIX 5, 6, 7: Org-Aware Boosting & Demotion ---
        section = "secondary" # Default to secondary
        
        if person_detection.get("query_type") == "leadership_list" or person_detection.get("query_type") == "team_list":
            
            # 2. Check Title Validity (Fix 7 + Change 4: semantic/fuzzy role matching)
            if is_internal:
                title_valid = is_leadership_role(title) if title else False
                if title_valid:
                    # FIX 7: Org match + title -> leadership
                    boost *= 2.0
                    if "director" in title.lower() or "founder" in title.lower():
                        boost *= 1.2
                    section = "primary"
                    leadership_detected = True
                else:
                    # Internal but invalid/low title
                    boost *= 0.8 # Slight demotion
            
            elif is_external:
                # Fix 6: Demote, don't skip
                boost *= 0.1
                section = "secondary"
                logger.info(f"Demoted external leader: {name}")
                
            else:
                # Unknown Org (Neutral)
                # Fix: Never primary if no org match
                boost *= 0.5
                section = "secondary"
                
        # --- Standard Relevance Logic (Preserved) ---
        
        # 1. Content Quality
        quality = metadata.get("content_quality_score", 0.7)
        boost *= (0.8 + 0.2 * quality)
        
        # 2. Person Name Exact Match (Always boost if looking for person)
        if person_detection.get("is_person_query") and query_name:
             if name and normalize_text(query_name) in normalize_text(name):
                 boost *= 3.0
                 if metadata.get("chunk_type") == "person_profile":
                     boost *= 1.5
                     if person_detection.get("query_type") == "specific_person":
                         section = "primary"
        
        # 3. Procedural Relevance
        if query_classification.get("query_type") == "procedural":
            if metadata.get("chunk_type") == "procedural":
                boost *= 1.3
                
        # 4. Recency (if available)
        age = metadata.get("content_age_days")
        if age is not None:
            if age < 30:
                boost *= 1.15
            elif age > 365:
                boost *= 0.95
                
        # 5. Keyword Overlap
        kw_score = get_keyword_score(metadata.get("text", ""), query)
        if kw_score > 0:
            boost *= (1.0 + 0.4 * kw_score) # Up to 40% boost for high overlap
            
        # 6. Fuzzy Name Match
        if person_detection.get("is_person_query") and person_detection.get("person_name"):
            # Check meta name
            meta_name = metadata.get("person_name")
            meta_title = metadata.get("person_title")
            
            if meta_name:
                f_score = fuzzy_match(person_detection.get("person_name"), meta_name)
                if f_score > 0.85: # High confidence typo match
                    boost *= 1.2
            
            # Check role title fuzzily
            if person_detection.get("role_title"):
                meta_title = metadata.get("person_title")
                if meta_title:
                    f_score = fuzzy_match(person_detection.get("role_title"), meta_title)
                    if f_score > 0.85:
                        boost *= 1.15
            
            # FIX 3: Collect fuzzy matches for "Did you mean...?"
            if query_name and meta_name:
                f_score = fuzzy_match(query_name, meta_name)
                if 0.7 <= f_score < 0.95: # Close match but not exact
                    fuzzy_matches.append({
                        "name": meta_name,
                        "title": meta_title or "Staff",
                        "score": f_score
                    })

        # 7. AI Classifier Integration (Fallthrough for non-explicit cases)
        # Only run if we haven't already decided it's external/internal via heuristic
        # If leadership_detected is True, we already boosted it.
        
        if not leadership_detected and not is_external:
             is_leadership_query = person_detection.get("query_type") == "team_list" or person_detection.get("query_type") == "leadership_list"
             if (is_leadership_query or person_detection.get("role_title")) and name != "Unknown":
                 from app.services.leadership_classifier import leadership_classifier
                 
                 # Prepare input
                 page_type_meta = metadata.get("page_type", {})
                 p_type_str = page_type_meta.get("type") if isinstance(page_type_meta, dict) else str(page_type_meta)
                 
                 ai_input = {
                    "person_name": name,
                    "person_title": title or "",
                    "page_type": p_type_str,
                    "source_url": metadata.get("url", ""),
                    "text_snippet": metadata.get("text", "")[:300],
                    "chunk_count": person_counts.get(name, 1)
                 }
                 
                 # Strict Gating
                 # Strict Gating
                 # Fix 5 (Org-aware) & Fix 9 (Duplicate runs)
                 # Only run detailed AI check for internal candidates with relevant titles
                 run_ai_check = False
                 if is_internal and title:
                     t_lower = title.lower()
                     if any(t in t_lower for t in ALLOWED_LEADERSHIP_TITLES):
                         run_ai_check = True
                 
                 if run_ai_check:
                     # Helper cache
                     ai_cache = kwargs.setdefault("_ai_cache", {})
                     cache_key = f"{name}:{title}"
                     
                     if cache_key in ai_cache:
                         ai_result = ai_cache[cache_key]
                     else:
                         ai_result = leadership_classifier.classify_leadership_role(ai_input)
                         ai_cache[cache_key] = ai_result
                         
                     ai_conf = ai_result.get("confidence", 0.0)
                     
                     if ai_conf > 0.8:
                         boost *= 1.5
                         logger.info(f"AI Boosted Legacy: {name} ({ai_conf})")

        # --- DIVERSITY & PENALTY LOGIC ---
        
        # 1. Duplicate URL Penalty
        url = metadata.get("url")
        if url:
            count = seen_urls.get(url, 0)
            seen_urls[url] = count + 1
            if count >= 3:
                boost *= 0.6  # Heavy penalty for 4th+ chunk from same doc
            elif count >= 2:
                boost *= 0.8  # Penalty for 3rd chunk
                
        # 2. Non-canonical penalty
        if not metadata.get("is_canonical", True):
            boost *= 0.8
            
        # 3. Person Diversity
        if person_detection.get("is_person_query") and metadata.get("chunk_type") == "person_profile":
             p_name = metadata.get("person_name", "unknown")
             p_count = seen_people.get(p_name, 0)
             seen_people[p_name] = p_count + 1
             
             # If we've already seen 3 distinct people, penalize others
             if len(seen_people) > 3 and p_count == 1:
                 boost *= 0.5
                 
             # Limit chunks per person
             if p_count >= 2:
                 boost *= 0.7 
                 
        # FIX 16: Role -> Person Matching (Embedding Similarity)
        if query_role_embedding is not None and title and embeddings_model:
            try:
                # Cache checking could be added here if needed
                title_embedding = embeddings_model.encode(title)
                
                # Cosine similarity
                if hasattr(embeddings_model, 'similarity'):
                     # fastembed might not have it exposed directly on model, usually just dot product for normalized
                     import numpy as np
                     sim = np.dot(query_role_embedding, title_embedding) / (np.linalg.norm(query_role_embedding) * np.linalg.norm(title_embedding))
                else:
                     # Manual cosine sim
                     import numpy as np
                     sim = np.dot(query_role_embedding, title_embedding) / (np.linalg.norm(query_role_embedding) * np.linalg.norm(title_embedding))
                
                if sim > 0.85:
                    logger.info(f"[ROLE MATCH] Strong match: '{person_detection.get('role_title')}' vs '{title}' ({sim:.3f})")
                    boost *= 2.5
                    section = "primary"
                    leadership_detected = True # If we found the role, we found leadership
                elif sim > 0.75:
                    logger.info(f"[ROLE MATCH] Weak match: '{person_detection.get('role_title')}' vs '{title}' ({sim:.3f})")
                    boost *= 1.3
                    
            except Exception as e:
                # logger.warning(f"Embedding sim failed: {e}")
                pass

        final_score = base_score * boost
        
        result["score"] = final_score
        result["boost_factor"] = round(boost, 3)
        result["section"] = section # FIX 7
        result["is_internal"] = is_internal
        result["is_external"] = is_external
        
        reranked.append(result)

    # Sort
    reranked.sort(key=lambda x: x["score"], reverse=True)
    
    if reranked:
        reranked[0]["person_detected"] = person_detected
        reranked[0]["leadership_detected"] = leadership_detected
        
        # Finalize person_presence
        person_presence["has_leadership_keyword"] = leadership_detected
        reranked[0]["person_presence"] = person_presence

    # FIX 3 (Production UX): If no good matches, inject the best fuzzy match into context
    if person_detection["is_person_query"] and person_detection["person_name"]:
        top_score = reranked[0].get("original_score", 0) * reranked[0].get("boost_factor", 1.0) if reranked else 0
        # If no exact match (exact match gives > 3.0 boost)
        if top_score < 2.0 and fuzzy_matches:
            # Sort fuzzy matches by score
            fuzzy_matches.sort(key=lambda x: x["score"], reverse=True)
            # Take the best one
            best = fuzzy_matches[0]
            # Add a "Recommendation" chunk to the reranked list so LLM knows about it
            reranked.insert(0, {
                "score": 0.999, # Force it to be top
                "payload": {
                    "is_suggestion": True,
                    "person_name": best["name"],
                    "person_title": best["title"],
                    "chunk_type": "person_profile",
                    "text": f"SYSTEM NOTE: The user searched for '{person_detection['person_name']}'. I couldn't find an exact match, but I found '{best['name']}' ({best['title']}). Please inform the user and ask if they meant this person."
                }
            })
            
    return reranked


def format_person_context(chunks: List[Dict], person_detection: Dict) -> str:
    """Format person chunks into structured context."""
    # Group by type
    profile_chunks = [c for c in chunks if c.get("payload", {}).get("chunk_type") == "person_profile"]
    other_chunks = [c for c in chunks if c.get("payload", {}).get("chunk_type") != "person_profile"]
    
    output = []
    
    if profile_chunks:
        output.append("# Specific Profile Matches")
        
        # Deduplication mapping
        unique_profiles = {}
        for chunk in profile_chunks:
            meta = chunk.get("payload", {})
            name = meta.get("person_name", "Unknown")
            # Keep the highest scoring chunk for each person
            if name not in unique_profiles or chunk.get("score", 0) > unique_profiles[name].get("score", 0):
                unique_profiles[name] = chunk

        for name, chunk in unique_profiles.items():
            meta = chunk.get("payload", {})
            url = meta.get("url", "#")
            title_text = meta.get("page_title", name)
            
            info = [f"## {name}"]
            info.append(f"Source: [{title_text}]({url})")
            
            if meta.get("person_title"): info.append(f"**Title:** {meta['person_title']}")
            if meta.get("person_department"): info.append(f"**Department:** {meta['person_department']}")
            text = chunk.get("text", "").strip()
            if text: info.append(f"\n{text}")
            
            # Contacts
            links = meta.get("person_social_links", {})
            contacts = []
            if meta.get("email"): contacts.append(f"Email: {meta['email']}")
            if links.get("linkedin"): contacts.append(f"LinkedIn: {links['linkedin']}")
            if contacts: info.append("\n**Contact:** " + ", ".join(contacts))
            
            output.append("\n".join(info) + "\n---")

    if other_chunks:
        output.append("\n# Related Information & Articles")
        for i, chunk in enumerate(other_chunks):
            meta = chunk.get("payload", {})
            title = meta.get("file_name") or meta.get("page_title") or f"Source {i+1}"
            url = meta.get("url", "#")
            text = chunk.get("text", "")
            
            output.append(f"### {title}\nSource: [{title}]({url})\n{text}\n---")
            
    return "\n\n".join(output) if output else "No specific person profile found."


def format_general_context(chunks: List[Dict]) -> str:
    """Standard context formatting with strict source lines."""
    parts = []
    for i, chunk in enumerate(chunks):
        meta = chunk.get("payload", {})
        
        # Improved title fallback logic
        title = meta.get("title") or meta.get("file_name") or meta.get("page_title")
        url = meta.get("url") or meta.get("canonical_url", "")
        
        if not title:
            if url and url != "#":
                # Use last part of URL as title if possible
                path = url.split('/')[-1]
                title = path if path else url
            else:
                title = f"Source {i+1}"
        
        # Ensure title is cleaned if it's still defaulting to "Unknown File" elsewhere
        if title == "Unknown File" and url:
             title = url.split('/')[-1] or url

        text = chunk.get("text", "")
        
        parts.append(f"### {title}\nSource: [{title}]({url if url else '#ID:' + meta.get('file_id', '')})\n{text}")
        
    return "\n\n---\n\n".join(parts)



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
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant for a knowledge base system. Your role is to respond naturally and conversationally based ONLY on the provided context.

Answering Rules:
- **Tone:** Professional, clear, and approachable.
- **Strict Sourcing:** You must cite your sources. Every piece of information should be traceable to a source provided in the context.
- **Citation Format:** At the end of your response, you MUST include a "Sources" section listing the files you used. Use the format: `[Title](URL)`.
- **No Hallucinations:** If the answer is not in the context, say "I don't have that information in the current knowledge base." Do NOT make up information.
- **Clarity:** Use bullet points for lists. Keep answers concise.

Context Usage:
- The context provided below contains snippets from documents.
- Each snippet starts with "Source: [Title](URL)" or similar metadata.
- Use this metadata to construct your citations.

Now, answer the user's question based strictly on the context below."""




# ============================================
# FOLLOW-UP HELPERS
# ============================================

def extract_topics_from_history(history: List[Dict]) -> List[str]:
    """Extract main topics from conversation history."""
    topics = []
    
    for msg in history:
        # Handle both dict and Pydantic models
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        
        if role == "user":
            # Extract capitalized phrases (likely topics/entities)
            # Simple extraction: 2+ word capitalized phrases
            capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
            topics.extend(capitalized)
    
    # Return unique topics
    return list(set(topics))[:5]


def extract_available_topics(chunks: List[Dict]) -> List[str]:
    """Extract main topics from retrieved chunks for suggestions."""
    topics = []
    
    for chunk in chunks:
        metadata = chunk.get("payload", {})
        
        # Get section hierarchy as topic
        section = metadata.get("section_hierarchy", "")
        if section:
            # Get last part of hierarchy (most specific)
            parts = section.split(">")
            if parts:
                topics.append(parts[-1].strip())
        
        # Get primary topic if available
        primary_topic = metadata.get("primary_topic", "")
        if primary_topic:
            topics.append(primary_topic)
        
        # Get key entities, ensuring it's a list
        entities = metadata.get("key_entities", [])
        if isinstance(entities, list):
            topics.extend(entities[:2])  # Top 2 entities per chunk
    
    # Deduplicate and return
    unique_topics = []
    seen = set()
    for topic in topics:
        if topic and topic.lower() not in seen:
            unique_topics.append(topic)
            seen.add(topic.lower())
    
    return unique_topics[:10]  # Max 10 topics


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

        # Person cache for fuzzy matching
        self.known_person_cache = []
        self.last_person_fetch_time = 0

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
            "is_generic": True,
            "answer_mode": "FULL"
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
        
        # Remove trailing horizontal rule separators (---) that sometimes appear
        cleaned_response = re.sub(r'\s*-{3,}\s*$', '', cleaned_response).strip()
        
        return {"answer": cleaned_response, "is_generic": is_generic}

    def _fetch_known_people(self) -> List[str]:
        """Fetch all known person names from vector store with caching."""
        import time
        current_time = time.time()
        
        # Cache for 1 hour (3600 seconds)
        if hasattr(self, "known_person_cache") and self.known_person_cache and (current_time - getattr(self, "last_person_fetch_time", 0) < 3600):
            return self.known_person_cache
            
        try:
            # Fetch from vector store if initialized
            if not self.vector_store:
                return []

            names = self.vector_store.get_all_unique_values(
                field="person_name", 
                filter_key="chunk_type", 
                filter_value="person_profile"
            )
            
            # Filter valid names
            valid_names = [n for n in names if n and isinstance(n, str) and len(n.split()) >= 1]
            
            self.known_person_cache = valid_names
            self.last_person_fetch_time = current_time
            logger.info(f"Refreshed known person cache: {len(valid_names)} people found")
            return valid_names
        except Exception as e:
            logger.error(f"Failed to fetch known people: {e}")
            return getattr(self, "known_person_cache", [])

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

    def retrieve_chunks(
        self, 
        query: str, 
        top_k: int = 5, 
        collection_id: Optional[str] = None, 
        prior_context: Optional[Dict] = None,
        request_cache: Optional[Dict] = None 
    ) -> List[Dict]:
        """Search vector DB and return top matching chunks with metadata.
        
        Enhancements:
        - Query Classification & Person Detection
        - Metadata Filtering
        - Advanced Reranking & Diversity
        - FIX 20: Request-Level Caching
        """
        # FIX 20: Check Cache
        if request_cache is not None:
             cache_key = f"retrieve:{query}:{collection_id}:{top_k}"
             if cache_key in request_cache:
                 logger.info(f"[RAG CACHE] Hit for query: {query}")
                 return request_cache[cache_key]

        # Handle None collection_id properly
        collection_id_str = collection_id if collection_id is not None else None
        
        # Step 1: Analyze Query
        # Fetch known people for fuzzy correction
        known_people = self._fetch_known_people()

        # Normalize strictly for classification and logic
        normalized_query = normalize_text(query)
        
        query_classification = classify_query(normalized_query)
        
        # FIX 1: Lock target organisation early
        # Currently hardcoded to 'polus' as per instructions ("Polus present -> ALWAYS internal")
        target_org = "polus"
        rag_state = {
            "intent": query_classification.get("query_type"),
            "target_org": target_org,
            "target_org_confidence": 0.95
        }

        
        # Pass query_type into detect_person_query via prior_context if not already there
        merged_context = prior_context or {}
        if "query_type" not in merged_context:
            merged_context = merged_context.copy()
            merged_context["query_type"] = query_classification["query_type"]
            
        person_detection = detect_person_query(normalized_query, prior_context=merged_context, known_people=known_people)
        
        logger.info(
            f"[RAG ANALYSIS] Type: {query_classification['query_type']}, Person: {person_detection['is_person_query']}",
            extra={
                "original_query": query,
                "normalized_query": normalized_query
            }
        )
        if person_detection.get('is_person_query'):
            logger.info(f"[RAG PERSON] Name: {person_detection.get('person_name')}, Title: {person_detection.get('role_title')}")
            
        # Step 2: Adjust Retrieval Parameters (Change 1: intent-aware thresholds)
        search_top_k = top_k
        min_score = getattr(settings, "RAG_MIN_SCORE", GENERAL_MIN_SCORE)
        
        # Dynamic adjustments
        if person_detection["is_person_query"]:
            search_top_k = 20 # Fetch more for person queries to ensure we find the right profile
            min_score = 0.15  # Lower threshold to capture potential matches before reranking
        elif query_classification["query_type"] == "leadership_list":
            min_score = getattr(settings, "RAG_LEADERSHIP_MIN_SCORE", LEADERSHIP_MIN_SCORE)  # 0.15 for leadership
        elif query_classification["query_type"] == "factual":
            min_score = 0.30  # Higher precision for facts
        elif query_classification["query_type"] == "procedural":
            search_top_k = 15 # More context for steps
            
        # Step 3: Build Filters (Soft filtering enabled)
        filters = build_retrieval_filters(
            collection_id=collection_id_str,
            query_classification=query_classification,
            person_detection=person_detection,
            soft=True
        )
        
        # Step 4: Perform Search (with Mutation/Expansion)
        # Keep existing expansion logic but simplified
        expanded_queries = [query]
        
        # Add basic expansion if relevant
        # Add basic expansion if relevant
        if person_detection["person_name"]:
             expanded_queries.append(person_detection["person_name"])
             # --- FIX 2: START REMOVED AUTOMATIC LEADERSHIP EXPANSION ---
             # expanded_queries.append("leadership team management executives")
             # expanded_queries.append("CEO CTO Founder Director President")
             # --- FIX 2: END REMOVED AUTOMATIC LEADERSHIP EXPANSION ---
             
        elif query_classification["query_type"] == "leadership_list":
             # FIX 4: Role-first retrieval strategy
             # Search for role + org
             org_scope = prior_context.get("scope", "") if prior_context else ""
             expanded_queries.append(f"directors and leadership at {org_scope}")
             expanded_queries.append(f"management board executives {org_scope}")
             expanded_queries.append(f"vp head director {org_scope}")
             
        elif query_classification["query_type"] == "role_lookup":
             # --- FIX 3: Role Lookup Expansion ---
             role = person_detection.get("role_title", "staff")
             expanded_queries.append(f"{role} manager lead head")
             expanded_queries.append(f"{role} department team contact")
             # CRITICAL: Do NOT add generic leadership terms here
             
        elif query_classification["query_type"] == "factual":
             # Minimal expansion for factual queries
             pass
        else:
             # Basic keyword expansion for other types
             if len(query.split()) < 4:
                 expanded_queries.append(query + " details")
        
        # Limit expansions
        expanded_queries = expanded_queries[:5]
        
        all_results = []
        seen_ids = set()
        
        for q in expanded_queries:
            # We fetch more results than needed to allow for reranking
            # IMPORTANT: Reverting to non-filtered vector search if filtered search fails/timeouts
            # Or just doing Python-side filtering for robustness (since it worked before)
            try:
                # First try with basic collection filter only (lightest)
                results = self.vector_store.search(
                    q, 
                    top_k=search_top_k * 2, 
                    collection_id=collection_id_str
                )
            except Exception as e:
                logger.warning(f"[RAG SEARCH] Filtered search failed: {e}. Falling back to raw search.")
                results = self.vector_store.search(q, top_k=search_top_k * 4)
            
            for r in results:
                payload = r.get("payload", {})
                
                # Precise Python-side collection filtering for safety
                if collection_id_str:
                    p_coll = payload.get("collection_id")
                    if not p_coll or str(p_coll) != str(collection_id_str):
                        continue

                # Deduplicate by ID if available, otherwise by text hash
                res_id = r.get("id") or hash(payload.get("text", ""))
                
                if res_id not in seen_ids:
                    seen_ids.add(res_id)
                    all_results.append(r)
                    
        logger.info(f"[RAG RETRIEVE] Retrieved {len(all_results)} raw results after Python filtering")

        # Step 5: Rerank Results
        # Reranking logic is already robust (handles missing metadata)
        reranked_results = rerank_results(
            all_results, 
            query, 
            query_classification, 
            person_detection,
            query_org=prior_context.get("scope") if prior_context else None,
            rag_state=rag_state,  # Pass the locked org state
            embeddings_model=self.vector_store.embeddings if self.vector_store else None # FIX 16
        )
        
        # Step 6: Filter by Score & Final Top-K
        final_results = []
        for r in reranked_results:
            if r["score"] >= min_score:
                final_results.append(r)
                
        # Hard limit
        final_results = final_results[:top_k]
        
        logger.info(f"[RAG FINAL] Selected {len(final_results)} chunks after reranking (Top-K: {top_k})")
        if final_results:
             logger.info(f"[RAG SCORE] Top score: {final_results[0]['score']:.4f}")
             
        # Format for return
        chunks_with_sources = []
        for r in final_results:
            payload = r.get("payload", {})
            score = r.get("score", 0)
            
            # REQUIREMENT: If it can't be downloaded or visited, don't show (and don't give to LLM)
            file_id = payload.get("file_id", "")
            url = payload.get("url", "") or payload.get("canonical_url", "")
            
            if not file_id and not url:
                logger.warning(f"[RAG RETRIEVE] Skipping chunk with no file_id or url to prevent 'Unknown File' sources.")
                continue

            # Improved filename fallback
            file_name = payload.get("file_name")
            if not file_name or file_name == "Unknown File":
                file_name = payload.get("title") or payload.get("page_title")
                if not file_name and url:
                    # Clean fallback from URL
                    file_name = url.split('/')[-1] or url
                if not file_name:
                    file_name = "Relevant Document"
            
            chunks_with_sources.append({
                "text": payload.get("text", ""),
                "file_name": file_name,
                "file_id": file_id,
                "chunk_index": payload.get("chunk_index", 0),
                "source_type": payload.get("source_type", "file"),
                "url": url,
                "canonical_url": url,
                "score": score,
                "payload": payload, # Pass full payload for formatting later
                # Analysis metadata
                "metadata": {
                    "vector_score": r.get("original_score", 0),
                    "boost_factor": r.get("boost_factor", 1.0),
                    "query_type": query_classification["query_type"],
                    "person_detected": r.get("person_detected"),
                    "leadership_detected": r.get("leadership_detected"),
                    "person_presence": r.get("person_presence")
                }
            })
        
        # FIX 20: Populate Cache
        if request_cache is not None:
             request_cache[cache_key] = chunks_with_sources

        return chunks_with_sources

    # ------------------------------------------------------------------
    # Follow-up Question Detection and Generation
    # ------------------------------------------------------------------
    
    def needs_followup(
        self,
        query: str,
        chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
        query_classification: Optional[Dict] = None,
        person_detection: Optional[Dict] = None,
        conversation_state: Optional[Dict] = None # New Arg
    ) -> Dict[str, Any]:
        """
        Determine if the chatbot should ask a clarifying question.
        Returns a dict with 'needs_followup' (bool) and 'reason' (str).
        """
        # ─────────────────────────────────────────────────────────
        # FIX 6: STATE-BASED GATING (The "Hard Rule")
        # ─────────────────────────────────────────────────────────
        if conversation_state:
            # If we already resolved the Entity or have a strong Scope + Last Intent
            if conversation_state.get("active_entity") or (conversation_state.get("scope") and conversation_state.get("last_intent")):
                logger.info(f"[FOLLOWUP] Gating disabled due to resolved state: {conversation_state}")
                # We FORCE false, effectively trusting the RAG pipeline to have found the right chunks
                return {
                    "needs_followup": False,
                    "reason": "state_resolved",
                    "confidence": 1.0,
                    "suggested_topics": [],
                    "missing_context": []
                }

        # ─────────────────────────────────────────────────────────
        # RULE 0: Basic Validity Checks
        # ─────────────────────────────────────────────────────────
        
        # FIX 3: LEADERSHIP/EXECUTIVE INTENTS ARE COMPLETE
        kw = query.lower()
        # If query explicitly mentions "polus" or "directors", it's specific enough
        if "polus" in kw or "director" in kw or "leadership" in kw or "executive" in kw or "management team" in kw or (query_classification and query_classification.get("query_type") == "leadership_list"):
             return {
                "needs_followup": False,
                "reason": "leadership_intent_complete",
                "confidence": 1.0,
                "suggested_topics": [],
                "missing_context": []
            }
        result = {
            "needs_followup": False,
            "reason": None,
            "confidence": 0.0,
            "suggested_topics": [],
            "missing_context": []
        }
        
        if not query:
            return result

        # use normalized query for consistency
        try:
             normalized_query = normalize_text(query)
             query_lower = normalized_query # normalize_text already lowercases
        except Exception:
             normalized_query = query.lower().strip()
             query_lower = normalized_query
        
        # ─────────────────────────────────────────────────────────
        # RULE 1: Check conversation context for unresolved references
        # ─────────────────────────────────────────────────────────
        
        has_conversation = conversation_history and len(conversation_history) > 0
        
        # Pronouns without clear antecedent
        vague_pronouns = ["it", "this", "that", "these", "those", "them", "they"]
        
        # Improved regex-based detection
        contains_pronoun = any(re.search(rf"\b{p}\b", normalized_query) for p in vague_pronouns)
        starts_with_pronoun = any(normalized_query.startswith(p + " ") or normalized_query == p for p in vague_pronouns)
        
        if contains_pronoun or starts_with_pronoun:
            # Check if conversation history provides context
            if not has_conversation or len(conversation_history) < 2:
                result.update({
                    "needs_followup": True,
                    "reason": "vague_pronoun_no_context",
                    "confidence": 0.9,
                    "missing_context": ["What specific topic are you asking about?"]
                })
                # Placeholder for metric logging
                logger.info("[FOLLOWUP_METRIC] Triggered: vague_pronoun_no_context", extra={"query": query})
                return result
            
            # If conversation exists, check if pronoun reference is clear
            last_exchange = conversation_history[-2:]  # Last Q&A
            last_topics = extract_topics_from_history(last_exchange)
            
            if not last_topics:
                result.update({
                    "needs_followup": True,
                    "reason": "unclear_pronoun_reference",
                    "confidence": 0.8,
                    "missing_context": ["Which topic from our conversation are you referring to?"]
                })
                logger.info("[FOLLOWUP_METRIC] Triggered: unclear_pronoun_reference", extra={"query": query})
                return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 2: Detect incomplete or fragmented queries
        # ─────────────────────────────────────────────────────────
        
        incomplete_patterns = [
            r"^(what about|how about|and)\s",  # "what about...", "and..."
            r"^(more|else|also)\s",             # "more on...", "also..."
            r"^(the|a)\s\w+\s*$",               # Just "the thing" with no verb
            r"^\w+\s*\?*$"                      # Single word queries
        ]
        
        for pattern in incomplete_patterns:
            if re.match(pattern, query_lower):
                result.update({
                    "needs_followup": True,
                    "reason": "incomplete_query",
                    "confidence": 0.85,
                    "missing_context": ["Could you provide more details about what you'd like to know?"]
                })
                logger.info("[FOLLOWUP_METRIC] Triggered: incomplete_query", extra={"query": query})
                return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 3: No chunks found - check if query is valid
        # ─────────────────────────────────────────────────────────
        
        if not chunks or len(chunks) == 0:
            # If it's a person query but no people found
            if person_detection and person_detection.get("is_person_query"):
                person_name = person_detection.get("person_name")
                role_title = person_detection.get("role_title")
                
                if person_name:
                    result.update({
                        "needs_followup": True,
                        "reason": "person_not_found",
                        "confidence": 0.7,
                        "missing_context": [
                            f"I couldn't find information about '{person_name}' in our knowledge base.",
                            "Could you verify the name spelling or provide their role/department?"
                        ]
                    })
                    return result
                
                if role_title:
                    result.update({
                        "needs_followup": True,
                        "reason": "role_not_found",
                        "confidence": 0.7,
                        "missing_context": [
                            f"I couldn't find who holds the '{role_title}' position.",
                            "Could you provide more context or check the title?"
                        ]
                    })
                    return result
            
            # General query with no results - query might be too vague
            if len(query.split()) < 3:
                result.update({
                    "needs_followup": True,
                    "reason": "query_too_vague_no_results",
                    "confidence": 0.75,
                    "missing_context": ["Could you provide more specific details about what you're looking for?"]
                })
                return result
            
            # Don't trigger follow-up - let it generate "not found" answer
            return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 4: Low relevance scores (existing logic enhanced)
        # ─────────────────────────────────────────────────────────
        
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
        max_score = max(c.get("score", 0) for c in chunks)
        
        # Adjust threshold based on query type (Change 1: leadership uses lower bar)
        min_score_threshold = getattr(settings, "RAG_MIN_SCORE", 0.35)
        
        if query_classification:
            qtype = query_classification.get("query_type")
            if qtype == "factual":
                min_score_threshold = 0.40  # Higher bar for factual
            elif qtype == "exploratory":
                min_score_threshold = 0.25  # Lower bar for exploratory
            elif qtype == "leadership_list":
                min_score_threshold = getattr(settings, "RAG_LEADERSHIP_MIN_SCORE", LEADERSHIP_MIN_SCORE)  # 0.15
        
        if max_score < min_score_threshold:
            # Low scores + ambiguous query = follow-up needed
            ambiguous_phrases = [
                "tell me more", "explain", "elaborate", "details",
                "information about", "anything", "something"
            ]
            
            is_ambiguous = any(phrase in query_lower for phrase in ambiguous_phrases)
            
            if is_ambiguous:
                # Extract topics from low-scoring chunks for suggestions
                topics = extract_available_topics(chunks[:5])
                
                result.update({
                    "needs_followup": True,
                    "reason": "low_relevance_ambiguous",
                    "confidence": 0.7,
                    "suggested_topics": topics[:3],  # Top 3 related topics
                    "missing_context": ["Your question is quite broad. What specific aspect are you interested in?"]
                })
                logger.info("[FOLLOWUP_METRIC] Triggered: low_relevance_ambiguous", extra={"query": query})
                return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 5: Multi-part or compound questions
        # ─────────────────────────────────────────────────────────
        
        # Detect questions with multiple parts
        question_markers = query_lower.count("?")
        and_or_markers = query_lower.count(" and ") + query_lower.count(" or ")
        
        if question_markers > 1 or (question_markers == 1 and and_or_markers >= 2):
            result.update({
                "needs_followup": True,
                "reason": "multi_part_question",
                "confidence": 0.65,
                "missing_context": [
                    "I notice you're asking about multiple things.",
                    "Which aspect would you like me to focus on first?"
                ]
            })
            return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 6: Context-dependent queries that need clarification
        # ─────────────────────────────────────────────────────────
        
        # Check if query mentions concepts that require additional context
        if query_classification and query_classification.get("query_type") == "procedural":
            # "How to" questions missing important context
            procedural_keywords = ["configure", "setup", "install", "implement"]
            has_procedural_keyword = any(kw in query_lower for kw in procedural_keywords)
            
            if has_procedural_keyword:
                # Check if critical context is missing (platform, version, environment)
                context_markers = ["windows", "linux", "mac", "version", "environment", "production", "development"]
                has_context = any(marker in query_lower for marker in context_markers)
                
                if not has_context and avg_score < 0.5:
                    result.update({
                        "needs_followup": True,
                        "reason": "procedural_missing_context",
                        "confidence": 0.6,
                        "missing_context": [
                            "To provide accurate setup instructions, I need more details.",
                            "What platform/environment are you working with?"
                        ]
                    })
                    return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 7: Domain-specific context requirements (P0 FIX)
        # ─────────────────────────────────────────────────────────
        
        # Check if chunks mention specific domains that need context
        chunk_texts = " ".join([c.get("payload", {}).get("text", "") for c in chunks[:3]])
        
        # Domain-specific patterns that often need clarification
        domain_patterns = {
            "version": ["Which version are you using?", "Version-specific details might apply."],
            "plan": ["Which plan or tier are you on?", "Features vary by plan."],
            "role": ["What's your role or permission level?", "Access might differ by role."]
        }
        
        for keyword, questions in domain_patterns.items():
            if keyword in chunk_texts.lower() and keyword not in query_lower:
                # P0 FIX: Difference between missing context (FOLLOWUP) and domain mismatch (PARTIAL)
                # If intent is exploratory/overview, prefer PARTIAL answer
                if query_classification and query_classification.get("query_type") in ["exploratory", "overview", "history"]:
                    logger.info(f"[FOLLOWUP] Domain mismatch detected ({keyword}) but intent is exploratory. Switching to PARTIAL_TRANSPARENT.")
                    return {
                        "needs_followup": False,
                        "reason": "domain_mismatch_partial",
                        "confidence": 0.0,
                        "missing_context": []
                    }
                
                # Otherwise, strict follow-up for procedural/specific queries
                result.update({
                    "needs_followup": True,
                    "reason": f"missing_{keyword}_context",
                    "confidence": 0.55,
                    "missing_context": questions
                })
                return result
        
        # ─────────────────────────────────────────────────────────
        # RULE 8: Clear Query Override (P2 FIX)
        # ─────────────────────────────────────────────────────────
        if self._is_clear_query(query) and chunks and len(chunks) > 0:
            # If we have a clear query and chunks, avoid nitpicking follow-ups
            # (Unless explicitly caught by above strict rules)
            current_max = max(c.get("score", 0) for c in chunks)
            if current_max > 0.45:
                logger.info("[FOLLOWUP] Query is clear and has relevant chunks. Skipping verification.")
                result["needs_followup"] = False
                result["reason"] = "confident"
                return result
        
        # ─────────────────────────────────────────────────────────
        # No follow-up needed
        # ─────────────────────────────────────────────────────────
        
        result["reason"] = "confident"
        return result

    def _is_clear_query(self, question: str) -> bool:
        """
        Determine if a query is clear and specific (not ambiguous).
        
        A clear query:
        - Has specific nouns/entities (not just pronouns)
        - Is longer than 2 words
        - Doesn't rely on external context
        
        Returns:
            bool: True if the query is clear and specific
        """
        if not question:
            return False
        
        normalized = question.strip().lower()
        words = normalized.split()
        
        # Very short queries are often ambiguous
        if len(words) < 3:
            return False
        
        # Check for vague pronouns as the main subject
        vague_subjects = {"it", "this", "that", "these", "those", "they", "them"}
        
        # If query starts with or primarily uses vague pronouns, it's not clear
        if words[0] in vague_subjects:
            return False
        
        # Check if the query has at least one specific noun (not just function words)
        function_words = {
            "what", "how", "why", "when", "where", "who", "which",
            "is", "are", "was", "were", "do", "does", "did", "can", "could", "would", "should",
            "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by", "from",
            "it", "this", "that", "these", "those", "they", "them", "i", "me", "my", "you", "your",
            "and", "or", "but", "if", "then", "so", "be", "been", "being", "have", "has", "had",
            "about", "more", "some", "any", "all", "most", "other", "into", "over", "such"
        }
        
        # Count meaningful words (not function words)
        meaningful_words = [w for w in words if w not in function_words and len(w) > 2]
        
        # Need at least 1 meaningful word for a clear query
        if len(meaningful_words) < 1:
            return False
        
        # Check for ambiguous standalone phrases
        ambiguous_phrases = {
            "tell me more", "explain this", "what about", "more details",
            "explain that", "what is it", "how does it work"
        }
        if normalized in ambiguous_phrases:
            return False
        
        return True

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

    def _generate_followup_questions_deprecated(self, question: str, chunks: list, reason: str) -> str:
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
1. Keep each question to ONE sentence.
2. Offer specific options based on the available topics if possible (e.g., "Are you asking about [Topic A] or [Topic B]?").
3. Be professional yet friendly.
4. Do NOT try to answer the original question.
5. Do NOT provide an empty response.
6. The questions should help you narrow down which part of the knowledge base to search.

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

    def generate_followup_questions(
        self,
        query: str,
        followup_result: Dict,
        chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ) -> List[str]:
        """
        Generate intelligent, context-aware follow-up questions.
        
        Uses AI to generate specific, helpful questions based on:
        - Why follow-up is needed (reason)
        - Available content in KB (chunks)
        - Conversation context
        - Suggested topics
        """
        
        reason = followup_result.get("reason")
        suggested_topics = followup_result.get("suggested_topics", [])
        missing_context = followup_result.get("missing_context", [])
        
        # ─────────────────────────────────────────────────────────
        # Build context for AI
        # ─────────────────────────────────────────────────────────
        
        context_for_ai = f"User query: {query}\n\n"
        context_for_ai += f"Follow-up reason: {reason}\n\n"
        
        # Add available topics from KB
        if suggested_topics:
            context_for_ai += f"Related topics in knowledge base: {', '.join(suggested_topics)}\n\n"
        
        # Add snippet of available content
        if chunks:
            context_for_ai += "Available information includes:\n"
            for i, chunk in enumerate(chunks[:3], 1):
                text_preview = chunk.get("payload", {}).get("text", "")[:200]
                context_for_ai += f"{i}. {text_preview}...\n"
            context_for_ai += "\n"
        
        # Add conversation context if available
        if conversation_history and len(conversation_history) > 0:
            context_for_ai += "Recent conversation:\n"
            for msg in conversation_history[-4:]:  # Last 2 exchanges
                # Handle both dict and Pydantic models
                role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "user")
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                
                context_for_ai += f"{role.capitalize()}: {content[:150]}\n"
            context_for_ai += "\n"
        
        # ─────────────────────────────────────────────────────────
        # Build AI prompt based on reason
        # ─────────────────────────────────────────────────────────
        
        prompts_by_reason = {
            "vague_pronoun_no_context": """
The user used a pronoun ('it', 'this', 'that') but there's no clear context about what they're referring to.

Generate 2 clarifying questions that:
1. Ask what specific topic/item they're referring to
2. Suggest possible topics from the knowledge base if available

Keep questions friendly and helpful.
""",
            
            "unclear_pronoun_reference": """
The user used a pronoun, but it's unclear which topic from our conversation they mean.

Generate 2 questions that:
1. Ask which specific aspect of the previous discussion they want to know about
2. List possible topics they might be referring to

Reference the recent conversation context.
""",
            
            "incomplete_query": """
The user's query is incomplete or fragmented (e.g., just "what about...", "and...").

Generate 2 questions that:
1. Ask them to complete their thought
2. Suggest what additional information would be helpful

Be encouraging and guide them to ask a complete question.
""",
            
            "person_not_found": """
The user asked about a person who is not in our knowledge base.

Generate 2 questions that:
1. Politely confirm the person's name spelling
2. Ask if they know the person's role, department, or any other identifying information

Be helpful and suggest alternative ways to find the person.
""",
            
            "role_not_found": """
The user asked about a role/position that we couldn't find.

Generate 2 questions that:
1. Ask them to clarify or rephrase the role/title
2. Suggest they might provide department or team name

Offer to help find the person another way.
""",
            
            "query_too_vague_no_results": """
The user's query is very short and vague, and we found no relevant results.

Generate 2 questions that:
1. Ask for more specific details about what they're looking for
2. Suggest they might rephrase with more keywords

Provide guidance on how to ask better questions.
""",
            
            "low_relevance_ambiguous": """
The user's query is broad/ambiguous and we only found low-relevance results.

Generate 2 questions that:
1. Ask what specific aspect they're interested in
2. Offer the suggested related topics as options: {topics}

Help narrow down their question to something we can answer well.
""",
            
            "multi_part_question": """
The user asked multiple questions at once.

Generate 2 questions that:
1. Acknowledge they asked about multiple things
2. Ask which aspect they'd like answered first
3. Optionally list the different parts we detected

Be organized and help them break down their question.
""",
            
            "procedural_missing_context": """
The user asked a "how-to" question but is missing important context (platform, version, environment).

Generate 2 questions that:
1. Ask for the missing context (which platform/version/environment)
2. Explain why this context matters for accurate instructions

Be professional and helpful.
""",
            
            "missing_version_context": """
The content mentions version-specific information, but the user didn't specify a version.

Generate 2 questions that:
1. Ask which version they're using
2. Explain that the answer may vary by version

Provide helpful context.
"""
        }
        
        # Get prompt template for this reason, or use default
        prompt_template = prompts_by_reason.get(reason, """
The user's query needs clarification.

Generate 2 helpful questions that:
1. Address the specific issue: {reason}
2. Guide them toward providing the missing information

Be helpful and specific.
""")
        
        # Replace placeholders
        if "{topics}" in prompt_template and suggested_topics:
            topics_str = ", ".join(suggested_topics[:5])
            prompt_template = prompt_template.replace("{topics}", topics_str)
        
        prompt_template = prompt_template.replace("{reason}", reason or "unclear query")
        
        # ─────────────────────────────────────────────────────────
        # Call AI to generate questions
        # ─────────────────────────────────────────────────────────
        
        full_prompt = context_for_ai + prompt_template + """

Generate exactly 2 clarifying questions. Format:
1. [First question]
2. [Second question]

Questions should be:
- Specific to the situation
- Helpful and actionable
- Friendly and professional
- Concise (one sentence each)
"""
        
        try:
            # Call existing AI function
            followup_text, _ = self.call_ai(
                prompt=full_prompt,
                max_tokens=200,
                temperature=0.7
            )
            
            # Parse response
            questions = []
            
            # Try to extract numbered questions
            lines = followup_text.strip().split("\n")
            for line in lines:
                # Match "1. Question?" or "- Question?" patterns
                match = re.match(r'^[\d\-\*\.]+\s*(.+)$', line.strip())
                if match:
                    question = match.group(1).strip()
                    if question and len(question) > 10:
                        questions.append(question)
            
            # If parsing failed, try splitting by punctuation
            if not questions:
                # Remove brackets [RESPONSE_TYPE...] first
                cleaned = re.sub(r'\[RESPONSE_TYPE:\w+\]', '', followup_text)
                sentences = re.split(r'[.!?]+', cleaned)
                questions = [s.strip() + "?" for s in sentences if len(s.strip()) > 10]
            
            if questions and len(questions) >= 1:
                logger.info(f"[FOLLOWUP] Generated questions: {len(questions)}")
                return questions[:2]
            
        except Exception as e:
            logger.warning(f"[FOLLOWUP] AI follow-up generation failed: {e}")
        
        # ─────────────────────────────────────────────────────────
        # Fallback: Use template-based questions
        # ─────────────────────────────────────────────────────────
        
        if missing_context:
            # Use the pre-generated missing_context questions
            return missing_context[:2]
        
        # Ultimate fallback
        fallback_questions = [
            "Could you provide more details about what you're looking for?",
            "What specific aspect would you like to know more about?"
        ]
        
        if suggested_topics:
            fallback_questions[1] = f"Are you asking about: {', '.join(suggested_topics[:3])}?"
        
        return fallback_questions

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

    def _resolve_prompt_settings(self, collection_id: Optional[str] = None, scope: Optional[str] = None, intent: Optional[str] = None, answer_mode: Optional[str] = None):
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
            
        # FIX 2: SCOPE INJECTION
        if scope:
             # Prevent "which company" questions by explicitly grounding the prompt
             system_prompt += f"\n\nIMPORTANT CONTEXT: The user is asking about '{scope}'. Assume all questions relate to {scope} unless specified otherwise."

        # FIX 10: INTENT-AWARE SYSTEM PROMPTS
        if intent:
            if intent in ["history", "overview", "exploratory"]:
                system_prompt += "\n\nRESPONSE GUIDELINE: Provide a high-level summary. Focus on narrative flow, key events, and broad concepts rather than minute details."
            elif intent in ["policy", "admin"]:
                system_prompt += "\n\nRESPONSE GUIDELINE: Be precise and authoritative. Quote relevant policy clauses where possible. Differentiate between strict rules and general guidelines."
            elif intent in ["people", "leadership"]:
                system_prompt += "\n\nRESPONSE GUIDELINE: Focus on role, responsibilities, and professional background. If multiple people match, list them clearly."
            elif intent in ["procedural", "troubleshooting"]:
                system_prompt += "\n\nRESPONSE GUIDELINE: Provide step-by-step instructions. Use numbered lists. Highlight any prerequisites or warnings."

        # FIX 1: PARTIAL ANSWER TRANSPARENCY
        if answer_mode == "PARTIAL_TRANSPARENT":
            system_prompt += "\n\nIMPORTANT: The available context might be from a different domain than requested (e.g., policy documents for a history question). You MUST explicitly acknowledge this limitation. Start or end by saying something like 'Based on the available [domain] documents...'"

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

    def _parse_ai_response(self, raw_text: str) -> Dict[str, Any]:
        """Parse the AI response to separate answer text from classification JSON."""
        default_response = {
            "answer": raw_text,
            "answer_mode": "FULL",
            "is_generic": False
        }
        
        if not raw_text:
            return default_response
            
        # Look for the last integer-like structure or JSON block
        # Our instruction asks for a JSON object on a new line at the end
        
        lines = raw_text.strip().split('\n')
        last_line = lines[-1].strip()
        
        if last_line.startswith('{') and last_line.endswith('}'):
            try:
                data = json.loads(last_line)
                # Reconstruct answer without the JSON line
                answer_text = '\n'.join(lines[:-1]).strip()
                return {
                    "answer": answer_text,
                    "answer_mode": data.get("answer_mode", "FULL"),
                    "is_generic": data.get("is_generic", False)
                }
            except json.JSONDecodeError:
                pass
                
        # Fallback: Look for [RESPONSE_TYPE:GENERIC] tag (legacy from previous prompts)
        if "[RESPONSE_TYPE:GENERIC]" in raw_text:
            return {
                "answer": raw_text.replace("[RESPONSE_TYPE:GENERIC]", "").strip(),
                "answer_mode": "GENERIC_ERROR",
                "is_generic": True
            }
            
        return default_response

    def answer(
        self, 
        query: str, 
        top_k: int = 5, 
        collection_id: Optional[str] = None, 
        prior_context: Optional[Dict] = None, 
        conversation_state: Optional[Dict] = None,
        request_cache: Optional[Dict] = None # FIX 20
    ) -> Union[str, Dict[str, any]]:
        """Main pipeline: retrieve → medium-detailed answer with source references using collection-specific prompt.
        
        Returns:
            dict with 'answer' (str) and 'is_generic' (bool) for AI classification
        """
        if self._is_small_talk(query):
            return self._handle_small_talk(query)

        chunks_with_sources = self.retrieve_chunks(
            query, 
            top_k=top_k, 
            collection_id=collection_id, 
            prior_context=prior_context,
            request_cache=request_cache # FIX 20
        )
        if not chunks_with_sources:
            return {
                "answer": "I wasn't able to retrieve a confident answer, please refine your question.",
                "is_generic": True
            }

        # Run classification for intent-aware prompts
        try:
             # normalized_query might be redundant but safely consistent
             normalized_query = normalize_text(query)
        except:
             normalized_query = query.lower().strip()
        
        query_classification = classify_query(normalized_query)
        intent = query_classification.get("query_type") if query_classification else None

        system_prompt, model, max_tokens, temperature = self._resolve_prompt_settings(
            collection_id=collection_id,
            scope=conversation_state.get("scope") if conversation_state else None,
            intent=intent,
            answer_mode="FULL" # 'answer' method usually implies full/direct answer
        )

        # Check for person data to adjust formatting
        person_chunks = [c for c in chunks_with_sources if c.get("payload", {}).get("chunk_type") == "person_profile"]
        has_person_data = len(person_chunks) > 0
        
        # Build context
        source_files = {}
        total_tokens = 0
        
        # Use appropriate formatter
        if has_person_data:
            # For person queries, we use a specialized formatter
            # We still need to populate source_files for the response
            # So we iterate chunks just to build source_files, but context string comes from formatter
            context = format_person_context(chunks_with_sources, detect_person_query(query, prior_context=prior_context))
            
            # Add person-specific instructions to prompt
            system_prompt += """
            
When answering questions about people:
- Present information in a clear, structured format
- Include: Full name, Title/Role, Department (if available)
- Add contact information if available (LinkedIn, email)
- Keep the tone professional and factual
- If multiple people match, list all relevant matches
"""
        else:
            # Standard formatting
            context = format_general_context(chunks_with_sources)
            
        # Build source_files dict (common for both paths)
        for i, chunk in enumerate(chunks_with_sources):
             file_name = chunk.get("file_name", "Unknown File")
             if file_name not in source_files:
                source_files[file_name] = {
                    'file_id': chunk.get('file_id', ''),
                    'source_type': chunk.get('source_type', 'file'),
                    'url': chunk.get('url', '') or chunk.get('canonical_url', ''),
                    'payload': chunk.get('payload', {}) # Store payload for API response
                }

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
        if True:  # Always show sources
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

        return {"answer": answer, "is_generic": is_generic, "tokens_used": tokens_used, "source_files": source_files}

    def answer_with_context(
        self,
        query: str,
        conversation_history: List,
        top_k: int = 5,
        collection_id: Optional[str] = None,
        prior_context: Optional[Dict] = None,
        conversation_state: Optional[Dict] = None, # New Arg
        request_cache: Optional[Dict] = None # FIX 20
    ) -> Union[str, Dict[str, any]]:
        """Main pipeline with conversation context: retrieve → contextual answer with source references.
        
        Returns:
            dict with 'answer' (str) and 'is_generic' (bool) for AI classification
        """
        if self._is_small_talk(query):
            return self._handle_small_talk(query)
            
        # FIX 4: AFFIRMATION HANDLING ("Yes", "Everything")
        # Reuse last intent if available
        if conversation_state and conversation_state.get("last_intent") == "leadership_list":
             normalized = query.lower().strip()
             affirmations = ["yes", "ya", "yeah", "yep", "sure", "correct", "everything", "all of them", "all"]
             if any(a in normalized for a in affirmations) or normalized in affirmations:
                 logger.info("[INTENT] Detected affirmation for Leadership List. Expanding query.")
                 # Rewrite query to force expansion
                 query = "detailed profiles of the leadership team executives"
                 # Force high retrieval count
                 top_k = 15 
        
        # Step 1: Analyze Query to prep for retrieval and follow-up
        try:
             # normalized_query might be redundant if retrieve_chunks does it, 
             # but we need it for pre-retrieval logic
             normalized_query = normalize_text(query)
        except:
             normalized_query = query.lower().strip()

        # FIX: Define query_classification before using it
        query_classification = classify_query(normalized_query)

        # Inject query_type and scope for detection and retrieval gating
        merged_context = prior_context or {}
        if "query_type" not in merged_context or (conversation_state and conversation_state.get("scope") and "scope" not in merged_context):
            merged_context = merged_context.copy()
            if "query_type" not in merged_context:
                merged_context["query_type"] = query_classification["query_type"]
            if conversation_state and conversation_state.get("scope") and "scope" not in merged_context:
                merged_context["scope"] = conversation_state.get("scope")
            
        person_detection = detect_person_query(normalized_query, prior_context=merged_context)
        query_name = person_detection.get("person_name")

        chunks_with_sources = self.retrieve_chunks(
            query, 
            top_k=top_k, 
            collection_id=collection_id, 
            prior_context=merged_context,
            request_cache=request_cache # FIX 20
        )
        
        # Step 2: Enhanced follow-up detection
        followup_result = self.needs_followup(
            query=query,
            chunks=chunks_with_sources,
            conversation_history=conversation_history,
            query_classification=query_classification,
            person_detection=person_detection,
            conversation_state=conversation_state 
        )
        
        # Leadership short-circuit: ONLY return path for leadership_list. Must run BEFORE answer_mode / NO_DATA.
        if (
            query_classification.get("query_type") == "leadership_list"
            and chunks_with_sources
        ):
            leadership_entities = extract_leadership_entities(
                chunks_with_sources, target_org=None, query_type="leadership_list"
            )
            top_score_val = chunks_with_sources[0].get("score", 0)
            if leadership_entities and top_score_val >= getattr(settings, "RAG_LEADERSHIP_MIN_SCORE", LEADERSHIP_MIN_SCORE):
                org_from_state = (conversation_state or {}).get("scope")
                inferred_org = org_from_state or infer_org_from_chunks(chunks_with_sources)
                org_display = inferred_org or "the organization"
                answer_text = generate_leadership_response(leadership_entities, top_score_val, org_display)
                source_files_lead = {}
                for chunk in chunks_with_sources:
                    fn = chunk.get("file_name", "Unknown File")
                    if fn not in source_files_lead:
                        source_files_lead[fn] = {
                            "file_id": chunk.get("file_id", ""),
                            "source_type": chunk.get("source_type", "file"),
                            "url": chunk.get("url", "") or chunk.get("canonical_url", ""),
                            "payload": chunk.get("payload", {}),
                        }
                source_list = []
                for file_name, info in sorted(source_files_lead.items()):
                    ref = info.get("url") if info.get("source_type") == "web_crawl" else info.get("file_id", "")
                    source_list.append(f"- [{file_name}]({ref}|{info.get('source_type', 'file')})")
                if source_list:
                    answer_text += "\n\n**Sources:**\n" + "\n".join(source_list)
                final_mode = AnswerMode.PARTIAL_TRANSPARENT if top_score_val < 0.25 else AnswerMode.FULL
                logger.info(f"[RAG LEADERSHIP] Short-circuit (score={top_score_val:.4f}, entities={len(leadership_entities)}, org={org_display})")
                return {
                    "answer": answer_text,
                    "is_generic": False,
                    "answer_mode": final_mode,
                    "sources": list(source_files_lead.keys()),
                    "chunk_count": len(chunks_with_sources),
                }
        
        # DETERMINE ANSWER MODE (Fix 4 & 8)
        person_detected = False
        leadership_detected = False
        target_org = "polus" # Consistent with system
        has_internal_data = False
        
        if chunks_with_sources:
             # Retrieve signals from reranker (stored in the first chunk's root)
             first_chunk = chunks_with_sources[0]
             
             # Use propagated flags from reranker
             person_detected = first_chunk.get("person_detected", False)
             leadership_detected = first_chunk.get("leadership_detected", False)
             
             # FIX 8: Check for ANY internal data
             for c in chunks_with_sources:
                 org = c.get("payload", {}).get("organization")
                 if org and normalize_text(org) == target_org:
                     has_internal_data = True
                     break
             
             # Fallback for person_detected
             if not person_detected and query_name:
                 query_name_norm = normalize_text(query_name)
                 for chunk in chunks_with_sources:
                     payload = chunk.get("payload", {})
                     p_name = payload.get("person_name")
                     if p_name and query_name_norm in normalize_text(p_name):
                         person_detected = True
                         break

        answer_mode = AnswerMode.FULL
        if followup_result.get("reason") == "domain_mismatch_partial":
            answer_mode = AnswerMode.PARTIAL_TRANSPARENT
        elif followup_result.get("needs_followup"):
            answer_mode = AnswerMode.FOLLOWUP
        else:
             # --- FIX 4: INTENT-AWARE ANSWER MODE ---
             # Priority 1: Existence check for Person/Role queries
             # If we found chunks for a specific person/role, we show them (FULL/PARTIAL), even if "internal" flag is missing.
             
             intent = person_detection.get("query_type") # e.g. "specific_person", "role_lookup"
             has_results = len(chunks_with_sources) > 0
             
             if intent == "role_lookup":
                 if has_results:
                      answer_mode = AnswerMode.FULL
                 else:
                      # STRICT FAIL: Role lookup with no results -> NO_DATA (or Followup if generated above)
                      # We explicitly want to avoid leadership fallback here.
                      answer_mode = AnswerMode.NO_DATA_CONFIRMED
                      
             elif person_detection.get("is_person_query"):
                 if has_results:
                     # If we have results and a person was detected in text, show it.
                     if person_detected:
                         answer_mode = AnswerMode.FULL
                         # Downgrade to PARTIAL if leadership was asked but not found?
                         # For now, consistent with "Fix 12", we want to show what we found.
                     else:
                         # Results exist but fuzzy match didn't confirm person name?
                         # This happens if we retrieved "Ramya" for query "Remya" (fuzzy success)
                         # Trust the retrieval if score is decent.
                         if chunks_with_sources[0].get("score", 0) > 0.4:
                              answer_mode = AnswerMode.FULL
                         else:
                              answer_mode = AnswerMode.NO_DATA_CONFIRMED
                 else:
                     answer_mode = AnswerMode.NO_DATA_CONFIRMED

             elif intent == "leadership_list":
                 # Change 1 & 2: Use top_score and accept partial leadership data
                 top_score_val = chunks_with_sources[0].get("score", 0) if chunks_with_sources else 0
                 leadership_entities = extract_leadership_entities(
                     chunks_with_sources, target_org=target_org, query_type="leadership_list"
                 ) if chunks_with_sources else []
                 if len(leadership_entities) >= 1:
                     if top_score_val >= 0.25:
                         answer_mode = AnswerMode.FULL
                     elif top_score_val >= LEADERSHIP_MIN_SCORE:
                         answer_mode = AnswerMode.PARTIAL_TRANSPARENT
                     else:
                         answer_mode = AnswerMode.NO_DATA_CONFIRMED
                 elif has_internal_data:
                     answer_mode = AnswerMode.FULL
                 elif has_results:
                     answer_mode = AnswerMode.PARTIAL_TRANSPARENT
                 else:
                     answer_mode = AnswerMode.NO_DATA_CONFIRMED
                     
             else:
                 # Default logic for other queries
                 if not has_internal_data and not has_results:
                      answer_mode = AnswerMode.NO_DATA_CONFIRMED
                 else:
                      answer_mode = AnswerMode.FULL
                      
        logger.info(f"[ANSWER_MODE] Selected mode: {answer_mode} (Intent: {person_detection.get('query_type')}, Results: {len(chunks_with_sources)})")
        
        # Step 3: If follow-up needed, generate questions
        # Enforce confidence threshold
        FOLLOWUP_CONFIDENCE_THRESHOLD = getattr(settings, "RAG_FOLLOWUP_CONFIDENCE_THRESHOLD", 0.6)
        
        if answer_mode == AnswerMode.FOLLOWUP and followup_result["confidence"] >= FOLLOWUP_CONFIDENCE_THRESHOLD:
            followup_questions = self.generate_followup_questions(
                query=query,
                followup_result=followup_result,
                chunks=chunks_with_sources,
                conversation_history=conversation_history
            )
            
            # Format follow-up response
            followup_text = "\n\n".join(followup_questions)
            
            return {
                "answer": followup_text,
                "is_followup": True,
                "is_generic": False, # Technically it's a specific follow-up
                "item_mode": AnswerMode.FOLLOWUP, # P5 FIX
                "answer_mode": AnswerMode.FOLLOWUP,
                "sources": [],
                "chunk_count": 0,
                "followup_reason": followup_result["reason"],
                "followup_confidence": followup_result["confidence"],
                "suggested_topics": followup_result.get("suggested_topics", [])
            }
        
        # If we had a potential follow-up but confidence was low, we fall through to FULL/PARTIAL answer logic
        
        # Fallback to standard generic response if chunks are missing but no follow-up triggered
        if not chunks_with_sources or answer_mode == AnswerMode.NO_DATA_CONFIRMED:
            if query_classification.get("query_type") == "leadership_list":
                # Never use raw scope: can be None → "None leadership". Always fallback.
                org_display = ((conversation_state or {}).get("scope") or "the organization")
                return {
                    "answer": f"I don't have information about {org_display} leadership in the knowledge base.",
                    "is_generic": True,
                    "answer_mode": AnswerMode.NO_DATA_CONFIRMED
                }
            return {
                "answer": f"I don't have sufficient information about {query_name or 'this person'} in the knowledge base." if person_detection.get("is_person_query") else "I wasn't able to retrieve a confident answer, please refine your question.",
                "is_generic": True,
                "answer_mode": AnswerMode.NO_DATA_CONFIRMED
            }

        system_prompt, model, max_tokens, temperature = self._resolve_prompt_settings(
            collection_id=collection_id,
            scope=conversation_state.get("scope") if conversation_state else None,
            intent=query_classification.get("query_type") if query_classification else None,
            answer_mode=answer_mode
        )

        # Build conversation context with summarization for long histories
        conversation_context = ""
        if conversation_history:
            history_length = len(conversation_history)
            
            # Check if we need to summarize older messages
            if history_length > SUMMARY_TRIGGER_THRESHOLD:
                # Split: older (summarize) + recent (verbatim)
                older_messages = conversation_history[:-MAX_VERBATIM_MESSAGES]
                recent_messages = conversation_history[-MAX_VERBATIM_MESSAGES:]
                
                # Generate summary
                summary = self.summarize_conversation(older_messages)
                
                # Build context
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

        # Check for person data to adjust formatting
        person_chunks = [c for c in chunks_with_sources if c.get("payload", {}).get("chunk_type") == "person_profile"]
        has_person_data = len(person_chunks) > 0
        
        # Base system prompt (from settings); may be extended for person queries
        prompt_header = system_prompt
        
        # Build context
        source_files = {}
        total_tokens = 0
        
        # Use appropriate formatter
        if has_person_data:
            context = format_person_context(chunks_with_sources, detect_person_query(query, prior_context=prior_context))
            # FIX 17: Enforce strict person formatting in prompt
            prompt_header += """
            
Response Guidelines for Person Queries:
- Use the provided 'PRIMARY PROFILES' as the main source of truth.
- Format the answer clearly: Name, Title, Organization.
- If multiple people match, list them all.
- If the role is found but no specific person is named in context, state that clearly (ROLE_PRESENT_NO_OWNER).
"""
        else:
            context = format_general_context(chunks_with_sources)
            
        # FIX 17 & 22: Add classification instruction
        full_system_prompt = f"{prompt_header}\n\n{CLASSIFICATION_INSTRUCTION}"

        # Construct final user prompt
        user_prompt = f"""Context information is below.
---------------------
{context}
---------------------
Given the context information and not prior knowledge, answer the query.
Query: {query}
Answer:"""

        # Debug logging
        logger.info(f"[RAG AI CALL] Generating answer with mode={answer_mode}...")
        
        # Call AI
        raw_answer, tokens_used = self.call_ai(
            user_prompt, # Put everything in the prompt if system prompt is not supported by call_ai wrapper or merge them
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # FIX 17: Parsing Logic
        parsed = self._parse_ai_response(raw_answer)
        final_answer = parsed["answer"]
        ai_determined_mode = parsed["answer_mode"]
        is_generic = parsed["is_generic"]
        
        # Trust AI's "NoData" if we aren't already sure
        if ai_determined_mode == "NoData" and answer_mode != AnswerMode.NO_DATA_CONFIRMED:
             answer_mode = AnswerMode.NO_DATA_CONFIRMED
             
        # Fallback if AI failed to classify
        if is_generic and "error" in final_answer.lower():
             answer_mode = AnswerMode.NO_DATA_CONFIRMED

        # ALWAYS add formatted sources - remove any AI-generated sources section first
        final_answer = re.sub(r'(?:^|\n)\s*\**\s*\bSources?\b:?\s*\**\s*(?:\n[\s\S]*)?$', '', final_answer, flags=re.IGNORECASE).strip()
        
        # Build and append formatted sources ONLY if not a generic response
        if True:  # Always show sources
            source_list = []
            for file_name, info in sorted(source_files.items()):
                source_type = info.get('source_type', 'file')
                if source_type == 'web_crawl' and info.get('url'):
                    reference = info['url']
                else:
                    reference = info.get('file_id', '')
                source_list.append(f"- [{file_name}]({reference}|{source_type})")
            
            if source_list:
                final_answer += f"\n\n**Sources:**\n" + "\n".join(source_list)

        # Mask PARTIAL_TRANSPARENT from frontend to hide the warning banner
        # We still used it internally to shape the prompt.
        final_answer_mode = answer_mode
        if answer_mode == AnswerMode.PARTIAL_TRANSPARENT:
            final_answer_mode = AnswerMode.FULL

        return {
            "answer": final_answer, 
            "is_generic": is_generic, 
            "tokens_used": tokens_used, 
            "source_files": source_files, 
            "answer_mode": final_answer_mode,
            "person_presence": {
                "found": person_detected,
                "has_title": any(c.get("payload", {}).get("person_title") for c in chunks_with_sources),
                "has_leadership_keyword": leadership_detected,
                "source_domains": list(set(c.get("payload", {}).get("domain", "general") for c in chunks_with_sources))
            } if person_detection.get("is_person_query") else None
        }
