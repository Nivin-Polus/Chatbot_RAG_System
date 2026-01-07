"""Debug script to check if Pedro data exists in vector store"""
import warnings
warnings.filterwarnings('ignore')

from app.core.vectorstore import VectorStore
vs = VectorStore()

# Search for pedro
print("=" * 60)
print("Searching for 'pedro viejo'...")
results = vs.search("pedro viejo", top_k=10)
print(f"Found {len(results)} results")

for i, r in enumerate(results):
    score = r.get("score", 0)
    payload = r.get("payload", {})
    text = payload.get("text", "")[:300].replace("\n", " ")
    col_id = payload.get("collection_id", "N/A")
    source_type = payload.get("source_type", "N/A")
    file_name = payload.get("file_name", "N/A")
    print(f"\n{i+1}. Score: {score:.4f}")
    print(f"   Collection: {col_id}")
    print(f"   Source: {source_type}")
    print(f"   File: {file_name}")
    print(f"   Text: {text}...")

# Also search for just "pedro"
print("\n" + "=" * 60)
print("Searching for 'pedro'...")
results2 = vs.search("pedro", top_k=5)
print(f"Found {len(results2)} results")

for i, r in enumerate(results2):
    score = r.get("score", 0)
    payload = r.get("payload", {})
    text = payload.get("text", "")[:300].replace("\n", " ")
    col_id = payload.get("collection_id", "N/A")
    if "pedro" in text.lower():
        print(f"\n{i+1}. Score: {score:.4f} - CONTAINS PEDRO!")
        print(f"   Collection: {col_id}")
        print(f"   Text: {text}...")

# Check if any text in database contains "Pedro"
print("\n" + "=" * 60)
print("Searching for text containing 'Pedro'...")
# Do a broader search using person-related query
results3 = vs.search("Senior Business Analyst person contact", top_k=10)
for i, r in enumerate(results3):
    text = r.get("payload", {}).get("text", "")
    if "pedro" in text.lower() or "viejo" in text.lower():
        print(f"Found Pedro in result {i+1}!")
        print(f"   Score: {r.get('score', 0):.4f}")
        print(f"   Collection: {r.get('payload', {}).get('collection_id', 'N/A')}")
        print(f"   Text: {text[:400]}...")
