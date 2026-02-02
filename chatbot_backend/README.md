# Knowledge Base Chatbot Backend

## 🚀 Overview

A **RAG-based chatbot backend** built with FastAPI that processes documents, stores embeddings in Qdrant vector database, and provides intelligent answers using Claude LLM.

### ✨ Features
- 🔐 **JWT Authentication** with secure token-based access
- 📁 **File Management** - Upload, list, and delete documents (PDF, DOCX, PPTX, XLSX, TXT)
- 🔍 **Vector Search** - Semantic search using Qdrant vector database
- 🤖 **RAG Pipeline** - Retrieval-Augmented Generation with Claude AI
- 💬 **Context Management** - Maintains conversation context within sessions
- 🧠 **Session Tracking** - Unique session IDs for conversation continuity
- 🤔 **Intelligent Follow-Up Questions** - AI-generated clarifying questions for ambiguous queries
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

python start_server.py

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
| `POST` | `/chat/ask` | Ask question about documents | `Authorization: Bearer <token>` | See examples below |

**Basic Chat Example:**
```bash
curl -X POST "http://localhost:8000/chat/ask" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic of the uploaded documents?", "top_k": 5}'
```

**Chat with Context Example:**
```bash
curl -X POST "http://localhost:8000/chat/ask" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Can you explain more about that?",
    "session_id": "session_123456",
    "maintain_context": true,
    "conversation_history": [
      {"role": "user", "content": "What is the leave policy?", "timestamp": "2025-01-19T10:00:00Z"},
      {"role": "assistant", "content": "The leave policy includes...", "timestamp": "2025-01-19T10:00:05Z"}
    ],
    "top_k": 5
  }'
```

**Request Parameters:**
- `question` (required): The user's question
- `top_k` (optional): Number of document chunks to retrieve (default: 5)
- `session_id` (optional): Unique session identifier for context tracking
- `maintain_context` (optional): Boolean flag to enable context maintenance
- `conversation_history` (optional): Array of previous messages for context

**Response Format:**
```json
{
  "answer": "Contextual answer based on documents and conversation history",
  "session_id": "session_123456"
}
```

---

## 🤔 Intelligent Follow-Up Question System

### Overview
The chatbot includes an intelligent follow-up detection system that identifies when a user's query is ambiguous, lacks context, or has low relevance to the knowledge base. Instead of providing a low-confidence answer, the system asks clarifying questions to improve response quality.

### Detection Criteria

The follow-up system is triggered when any of these conditions are met:

1. **No Relevant Chunks**: Vector search returns zero matching documents
2. **Low Relevance Score**: Top chunk confidence below threshold (default: 0.35)
3. **Ambiguous Phrasing**: Questions with vague phrases like "tell me more", "explain this", "what about"
4. **Vague Pronouns**: Questions using "it", "this", "that" without clear referents
5. **Missing Critical Context**: Domain-specific rules detect missing required information

### Configuration

```env
# In .env file
SOURCE_MIN_SCORE=0.50  # Minimum score to show sources
# Follow-up threshold: 0.35 (hardcoded in rag.py)
```

**Threshold Guidelines:**
- 0.25-0.30: Very strict (more follow-ups)
- 0.35: Balanced (recommended)
- 0.40-0.50: Lenient (fewer follow-ups)

### Response Format

When follow-up is triggered:

```json
{
  "answer": null,
  "session_id": "session_123456",
  "is_followup": true,
  "followup_questions": "Could you specify which department's policy?",
  "followup_reason": "low_relevance_score",
  "sources": [],
  "chunk_count": 3
}
```

**Reason Codes:**
- `no_relevant_chunks`: No documents found
- `low_relevance_score`: Confidence too low
- `ambiguous_phrasing`: Vague question
- `vague_pronoun`: Unclear pronoun reference
- `missing_context`: Domain context missing

### Examples

**Example 1: Low Confidence**
```
User: "What's the policy?"
Top chunk score: 0.28 (below 0.35)
Response: "I'm not fully confident about which policy you're referring to. 
Are you asking about the leave policy, expense policy, or remote work policy?"
```

**Example 2: Vague Pronoun**
```
User: "How does it work?"
Detection: Pronoun without referent
Response: "What specific feature or process are you asking about?"
```

**Example 3: Missing Context**
```
User: "How do I install the software?"
Detection: "install" without platform
Response: "Which platform are you installing on? (Windows, Mac, Linux, or mobile?)"
```

### System Flow

```
User Question
    ↓
Vector Search
    ↓
Follow-Up Detection
    ↓
    ├─→ [Trigger Condition Met] → AI-Generated Follow-Up
    └─→ [Confident] → Generate Answer
```

### Customization

Add domain-specific rules in `app/core/rag.py`:

```python
domain_rules = [
    {
        "trigger_keywords": ["install", "upgrade"],
        "required_context": ["version", "windows", "mac"],
        "description": "installation query without platform"
    }
]
```

### Analytics

Follow-up events are logged:

```python
{
  "activity_type": "chat_followup_triggered",
  "user": "username",
  "details": {
    "question": "User's question",
    "reason": "low_relevance_score",
    "chunk_count": 3
  }
}
```

---

## 💬 Context Management

### Session-Based Conversations
The chatbot now supports maintaining conversation context within sessions:

- **Session IDs**: Each conversation gets a unique session identifier
- **Context Tracking**: Previous messages are included in AI prompts
- **Memory Limit**: Last 6 messages are used for context (configurable)
- **No Persistence**: Context is maintained only during active sessions

### How Context Works
1. **Frontend** generates unique session ID on chat start
2. **Each message** includes conversation history in request
3. **Backend** processes question with previous context
4. **AI model** receives both current question and conversation history
5. **Response** maintains conversational flow and references

### Context Request Structure
```json
{
  "question": "Current user question",
  "session_id": "unique_session_identifier",
  "maintain_context": true,
  "conversation_history": [
    {
      "role": "user",
      "content": "Previous user message",
      "timestamp": "2025-01-19T10:00:00Z"
    },
    {
      "role": "assistant", 
      "content": "Previous AI response",
      "timestamp": "2025-01-19T10:00:05Z"
    }
  ]
}
```

### Benefits
- **Natural Conversations**: Follow-up questions work properly
- **Reference Previous**: AI can refer to earlier parts of conversation
- **Better UX**: Users don't need to repeat context
- **Session Isolation**: Different sessions don't interfere

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