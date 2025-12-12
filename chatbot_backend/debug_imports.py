
try:
    print("Importing sqlalchemy...")
    import sqlalchemy
    print("sqlalchemy ok")
    
    print("Importing fastapi...")
    import fastapi
    print("fastapi ok")
    
    print("Importing uvicorn...")
    import uvicorn
    print("uvicorn ok")
    
    print("Importing anthropic...")
    import anthropic
    print("anthropic ok")
    
    print("Importing qdrant_client...")
    import qdrant_client
    print("qdrant_client ok")
    
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"FAILED with Exception: {type(e).__name__}: {e}")
