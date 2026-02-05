import re

def normalize_text(text: str) -> str:
    """
    Normalize text for matching and comparison ONLY.
    - Lowercase
    - Trim whitespace
    - Collapse multiple spaces
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text
