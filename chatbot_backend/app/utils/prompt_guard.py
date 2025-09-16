# app/utils/prompt_guard.py

import re

# Basic blacklist of abusive words (expandable)
BLACKLIST = [
    "hack", "kill", "attack", "exploit", "terrorist", "illegal"
]

def is_safe_prompt(prompt: str) -> bool:
    """
    Returns True if the prompt is safe, False if it contains blacklisted words.
    """
    prompt_lower = prompt.lower()
    for word in BLACKLIST:
        if re.search(rf"\b{word}\b", prompt_lower):
            return False
    return True
