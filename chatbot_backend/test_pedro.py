"""Test the improved RAG retrieval for 'who is pedro'"""
import warnings
warnings.filterwarnings('ignore')
import logging
logging.basicConfig(level=logging.INFO)

from app.core.rag import RAG

# Create RAG instance
rag = RAG()

# Test the query that was failing
print("=" * 60)
print("Testing: 'who is pedro'")
print("=" * 60)

# Note: Using no collection_id filter initially to test
chunks = rag.retrieve_chunks("who is pedro", top_k=5)

print(f"\nFound {len(chunks)} chunks")
for i, chunk in enumerate(chunks):
    text = chunk.get("text", "")[:300].replace("\n", " ")
    score = chunk.get("score", 0)
    file_name = chunk.get("file_name", "N/A")
    
    has_pedro = "pedro" in text.lower()
    print(f"\n{i+1}. Score: {score:.4f} {'[CONTAINS PEDRO!]' if has_pedro else ''}")
    print(f"   File: {file_name}")
    print(f"   Text: {text}...")
