# Knowledge Base Chatbot Backend (RAG + Claude + Qdrant)

## Overview

This backend provides a **RAG-based chatbot** that retrieves information from uploaded documents (PDF, DOCX, PPTX, XLSX, TXT), stores embeddings in **Qdrant**, and answers user questions using **Claude LLM**.  

Features include:

- File upload, deletion, and listing
- Vector-based semantic search (Qdrant)
- Optional Redis caching for frequently asked questions
- Prompt guardrails to prevent unsafe inputs
- JWT-based authentication
- Configurable via `.env`
- Fallback responses if Claude fails

---

## Folder Structure

app/
│
├── api/
│ ├── routes_auth.py # JWT authentication endpoints
│ ├── routes_files.py # Upload, delete, list files
│ ├── routes_chat.py # Chat endpoint integrating RAG + caching
│
├── core/
│ ├── rag.py # RAG pipeline, ask_AI (calls Claude)
│ ├── vectorstore.py # Qdrant integration
│ ├── embeddings.py # Text embeddings generation
│ └── cache.py # Redis cache wrapper (optional)
│
├── models/
│ └── file.py # File metadata Pydantic model
│
├── utils/
│ ├── file_parser.py # Parse PDF, DOCX, PPTX, XLSX, TXT
│ └── prompt_guard.py # Basic prompt safety filter
│
├── config.py # Configuration loaded from .env
└── main.py # FastAPI app initialization


---

## Setup

### 1. Clone the repo

```bash
git clone <repo_url>
cd knowledge-base-chatbot
```

### 2. Create virtual environment

python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

### 3.Install dependencies

```bash
pip install -r requirements.txt
```

## Dependencies include:

FastAPI

Uvicorn

Pydantic

python-dotenv

redis

requests

PyPDF2, python-docx, python-pptx, pandas

Qdrant client (qdrant-client)


## 4. Set up environment variables
Create a .env file in the root:

``` bash
# Claude
CLAUDE_API_KEY=<your_claude_api_key>
CLAUDE_API_URL=https://api.anthropic.com/v1/complete
CLAUDE_MODEL=claude-v1
CLAUDE_MAX_TOKENS=1000
CLAUDE_TEMPERATURE=0.0

# Vector DB (Qdrant)
VECTOR_DB_URL=http://localhost:6333

# Redis (optional)
USE_REDIS=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
CACHE_TTL_SECONDS=86400   # optional, default 24 hours

# JWT Auth
SECRET_KEY=<your_secret_key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App mode
APP_MODE=api

# File settings
MAX_FILE_SIZE_MB=25
ALLOWED_FILE_TYPES=pdf,docx,pptx,xlsx,txt

```

## 5. Run Qdrant

You can run Qdrant locally using Docker:

```bash
docker run -p 6333:6333 qdrant/qdrant