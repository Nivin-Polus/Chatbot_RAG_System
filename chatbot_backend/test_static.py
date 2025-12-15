"""Test content extraction after fix"""
from app.services.crawler.html_fetcher import fetch_static
from app.services.crawler.content_extractor import ContentExtractor

url = "https://policies.mit.edu/policy-topics/beginning-employment"

html = fetch_static(url)
print(f"HTML Length: {len(html)}")

extractor = ContentExtractor()
result = extractor.extract(html, url)

print(f"\n--- EXTRACTION RESULTS ---")
print(f"Title: {result.get('title', '')}")
print(f"Raw text length: {len(result.get('raw_text', ''))}")
print(f"Section count: {len(result.get('sections', []))}")
print(f"Word count: {result.get('word_count', 0)}")

raw_text = result.get('raw_text', '')
print(f"\n--- RAW TEXT PREVIEW ---")
print(raw_text[:800] if raw_text else "EMPTY!")
