
import sys
import os
import logging
from typing import Dict, Any

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.utils.text import normalize_text
from app.core.rag import classify_query, detect_person_query, fuzzy_match

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFICATION")

def test_normalize_text():
    logger.info("Testing normalize_text...")
    cases = [
        ("Hello World", "hello world"),
        ("  Spaces   ", "spaces"),
        ("MixED CaSe", "mixed case"),
        ("Tabs\tand\nNewlines", "tabs and newlines"),
        ("", "")
    ]
    for inp, expected in cases:
        result = normalize_text(inp)
        assert result == expected, f"Failed: '{inp}' -> '{result}' != '{expected}'"
    logger.info("✅ normalize_text passed")

def test_classify_query():
    logger.info("Testing classify_query...")
    # classify_query expects NORMALIZED input now
    cases = [
        ("who is ajin", "person"),
        ("contact details", "person"),
        ("what is rag", "factual"),
        ("how to install", "procedural"),
        ("system error", "troubleshooting"),
        ("claude vs gpt", "comparison")
    ]
    for inp, expected_type in cases:
        # Input is already normalized for the test case as per function requirement
        result = classify_query(inp)
        assert result["query_type"] == expected_type, f"Failed: '{inp}' -> {result['query_type']} != {expected_type}"
    logger.info("✅ classify_query passed")

def test_detect_person_query():
    logger.info("Testing detect_person_query...")
    # Expects NORMALIZED input
    cases = [
        ("who is ajin", "ajin", True),
        ("tell me about john doe", "john doe", True),
        ("contact sarah", "sarah", True),
        ("email bob smith", "bob smith", True),
        ("is alice the ceo", "alice", True), # Pattern extraction
        ("what is rag", None, False)
    ]
    
    for inp, expected_name, expected_is_person in cases:
        result = detect_person_query(inp)
        assert result["is_person_query"] == expected_is_person, f"Failed is_person: '{inp}' -> {result}"
        if expected_name:
            # Result name might be title cased or as extracted, let's check normalized
            assert normalize_text(result["person_name"]) == expected_name, f"Failed name: '{inp}' -> {result['person_name']} != {expected_name}"
            
    logger.info("✅ detect_person_query passed")

def test_fuzzy_match():
    logger.info("Testing fuzzy_match...")
    # fuzzy_match handles normalization internally
    score = fuzzy_match("Ajin", "ajin")
    assert score == 1.0, "Exact match failed"
    
    score = fuzzy_match("Ajin", "Aji n") # "aji n" -> "aji n" vs "ajin". Wait. normalize_text collapses spaces? "Aji n" -> "aji n". "Ajin" -> "ajin". They will differ.
    # "Aji n" normalized is "aji n". "Ajin" is "ajin".
    # SequenceMatcher ratio will be high but not 1.0.
    
    score = fuzzy_match("  Ajin  ", "ajin")
    assert score == 1.0, "Whitespace match failed"
    
    logger.info("✅ fuzzy_match passed")

if __name__ == "__main__":
    try:
        test_normalize_text()
        test_classify_query()
        test_detect_person_query()
        test_fuzzy_match()
        logger.info("\n🎉 ALL TESTS PASSED")
    except AssertionError as e:
        logger.error(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {e}")
        sys.exit(1)
