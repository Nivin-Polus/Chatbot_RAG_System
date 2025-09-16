# Knowledge Base Chatbot Backend

## 🚀 Overview

A **RAG-based chatbot backend** built with FastAPI that processes documents, stores embeddings in Qdrant vector database, and provides intelligent answers using Claude LLM.

### ✨ Features
- 🔐 **JWT Authentication** with secure token-based access
- 📁 **File Management** - Upload, list, and delete documents (PDF, DOCX, PPTX, XLSX, TXT)
- 🔍 **Vector Search** - Semantic search using Qdrant vector database
- 🤖 **RAG Pipeline** - Retrieval-Augmented Generation with Claude AI
- ⚡ **Redis Caching** - Optional caching for frequently asked questions
- 🛡️ **Security** - Prompt guardrails and input validation
- 🔧 **Configurable** - Environment-based configuration

---

## 📁 Project Structure

```
app/
├── api/
│   ├── routes_auth.py      # 🔐 Authentication endpoints
│   ├── routes_files.py     # 📁 File management endpoints
│   └── routes_chat.py      # 💬 Chat/RAG endpoints
├── core/
│   ├── auth.py            # 🔑 JWT & password utilities
│   ├── rag.py             # 🧠 RAG pipeline logic
│   ├── vectorstore.py     # 🗃️ Qdrant integration
│   ├── embeddings.py      # 🔢 Text embeddings
│   └── cache.py           # ⚡ Redis caching
├── models/
│   ├── user.py            # 👤 User models
│   └── file.py            # 📄 File metadata models
├── utils/
│   ├── file_parser.py     # 📖 Document parsing
│   └── prompt_guard.py    # 🛡️ Input validation
├── config.py              # ⚙️ Configuration management
└── main.py               # 🚀 FastAPI application
```

---

## 🛠️ Setup Instructions

### 1. Prerequisites
- **Python 3.10** (Required for compatibility with all dependencies)
- Docker (for Qdrant)
- Redis (optional, for caching)

### 2. Installation

```bash
# Clone and navigate to backend
cd chatbot_backend

# Create virtual environment with Python 3.10
py -3.10 -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

# Install dependencies (Rust-free!)
py -3.10 -m pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the backend root:

```env
# 🤖 Claude AI Configuration
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_MODEL=claude-3-haiku-20240307
CLAUDE_MAX_TOKENS=1000
CLAUDE_TEMPERATURE=0.0

# 🗃️ Qdrant Vector Database
VECTOR_DB_URL=http://localhost:6333

# ⚡ Redis Cache (Optional)
USE_REDIS=false
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 🔐 JWT Authentication
SECRET_KEY=your-super-secret-jwt-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 📁 File Upload Settings
MAX_FILE_SIZE_MB=25
ALLOWED_FILE_TYPES=pdf,docx,pptx,xlsx,txt

# 🚀 Application Mode
APP_MODE=api
```

### 4. Start Required Services

#### Qdrant Vector Database (Required)
```bash
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

#### Redis Cache (Optional)
```bash
docker run -p 6379:6379 redis:alpine
```

### 5. Run the Backend

```bash
# Using Python 3.10 directly
py -3.10 -m app.main

# Or using uvicorn with Python 3.10
py -3.10 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## 🔌 API Endpoints

### 🔐 Authentication
| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| `POST` | `/auth/token` | Login and get JWT token | `username`, `password` (form-data) |

**Example Login:**
```bash
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 📁 File Management
| Method | Endpoint | Description | Headers | Request Body |
|--------|----------|-------------|---------|--------------|
| `POST` | `/files/upload` | Upload document | `Authorization: Bearer <token>` | `uploaded_file` (multipart) |
| `GET` | `/files/list` | List all files | `Authorization: Bearer <token>` | - |
| `DELETE` | `/files/{file_id}` | Delete file | `Authorization: Bearer <token>` | - |

**Example File Upload:**
```bash
curl -X POST "http://localhost:8000/files/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "uploaded_file=@document.pdf"
```

### 💬 Chat/RAG
| Method | Endpoint | Description | Headers | Request Body |
|--------|----------|-------------|---------|--------------|
| `POST` | `/chat/ask` | Ask question about documents | `Authorization: Bearer <token>` | `{"question": "your question", "top_k": 5}` |

**Example Chat:**
```bash
curl -X POST "http://localhost:8000/chat/ask" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic of the uploaded documents?"}'
```

**Response Format:**
```json
{
  "summary": "Brief 2-3 bullet point answer",
  "detailed": "Comprehensive detailed answer with context"
}
```

---

## 🔑 JWT Token Usage

### Getting JWT Token
1. **Login** with credentials: `admin` / `admin123`
2. **Extract** the `access_token` from response
3. **Include** in all API calls: `Authorization: Bearer <token>`

### Token Expiration
- Default: 30 minutes
- Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`
- Frontend should handle token refresh

---

## 🗃️ Qdrant Setup

### Local Development
```bash
# Start Qdrant with persistent storage
docker run -p 6333:6333 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

### Production Setup
- Use Qdrant Cloud or self-hosted cluster
- Update `VECTOR_DB_URL` in `.env`
- Ensure network connectivity

### Collection Management
- Collections are created automatically
- Each uploaded file gets a unique collection
- Embeddings stored with metadata

---

## 📦 Dependencies (Rust-Free!)

### Core Framework
- `fastapi==0.109.0` - Web framework
- `uvicorn==0.25.0` - ASGI server
- `pydantic==2.5.2` - Data validation

### Authentication & Security
- `PyJWT==2.8.0` - JWT tokens (pure Python)
- `passlib==1.7.4` - Password hashing
- `argon2-cffi==23.1.0` - Argon2 hashing (pure Python)

### Document Processing
- `pypdf==3.17.4` - PDF parsing (pure Python)
- `python-docx==1.1.0` - Word documents
- `python-pptx>=0.6.21` - PowerPoint files
- `openpyxl==3.1.2` - Excel files

### AI & Vector Search
- `sentence-transformers>=2.2.2` - Text embeddings
- `qdrant-client>=1.7.1` - Vector database
- `anthropic==0.7.8` - Claude AI client

### Caching & Utilities
- `redis==5.0.1` - Caching (optional)
- `pandas>=2.0.0` - Data processing
- `requests>=2.31.0` - HTTP client

---

## 🚨 Troubleshooting

### Common Issues

1. **Qdrant Connection Error**
   ```bash
   # Check if Qdrant is running
   curl http://localhost:6333/health
   ```

2. **JWT Token Invalid**
   - Check token expiration
   - Verify `SECRET_KEY` in `.env`
   - Ensure proper Authorization header format

3. **File Upload Fails**
   - Check file size limits (`MAX_FILE_SIZE_MB`)
   - Verify file type is allowed (`ALLOWED_FILE_TYPES`)
   - Ensure proper multipart form data

4. **Claude API Errors**
   - Verify `CLAUDE_API_KEY` is valid
   - Check API rate limits
   - Ensure proper model configuration

### Health Checks
- **Backend**: `GET /health`
- **Qdrant**: `GET http://localhost:6333/health`
- **Redis**: `redis-cli ping`

---

## 🔧 Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black app/
isort app/
```

### Environment Variables
All configuration is handled via `.env` file - never commit secrets to version control!

---

## 📝 Default Credentials

**Username**: `admin`  
**Password**: `admin123`

⚠️ **Change these in production!** Update the password hash in `routes_auth.py`