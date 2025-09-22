# 🤖 Advanced RAG Chatbot System

A **production-ready Retrieval-Augmented Generation (RAG) chatbot system** with advanced conversation context management, role-based access control, and modern UI design. Built with React frontend and FastAPI backend.

## 🚀 System Overview

This enterprise-grade chatbot system enables organizations to create intelligent knowledge bases from their documents. Users can upload various document types and engage in natural, contextual conversations about the content. The system maintains conversation history, supports role-based access, and provides a beautiful, modern interface.

## ✨ **Complete Feature Set**

### 🧠 **Advanced AI & Context Management**
- **Contextual Conversations** - Maintains full conversation history within sessions
- **Session Management** - Unique session IDs for conversation continuity  
- **Follow-up Questions** - Natural conversation flow with reference to previous messages
- **Message Management** - Delete individual messages or conversation segments
- **Context Indicators** - Visual feedback showing conversation state
- **Smart Context Limits** - Uses last 6-10 messages for optimal performance

### 📁 **Document Management System**
- **Multi-format Support** - PDF, DOCX, PPTX, XLSX, TXT files
- **Drag & Drop Upload** - Modern file upload interface
- **File Cards Display** - Beautiful grid layout with file metadata
- **Bulk Operations** - Upload multiple files simultaneously
- **File Download** - Download original files from the knowledge base
- **File Deletion** - Remove files and associated vector embeddings
- **Storage Analytics** - Track file sizes and document counts

### 📋 **Activity Tracking System**
- **Real-time Activity Feed** - Track all user interactions and system events
- **Local Storage** - All activities stored locally (no external database required)
- **Activity Types** - File uploads, chat queries, session starts, file deletions
- **Statistics Dashboard** - Total files uploaded, chat sessions, queries count
- **Filter & Search** - Filter activities by type, user, or time period
- **Automatic Refresh** - Real-time updates every 30 seconds
- **Historical Data** - Keep activity history with automatic cleanup

### 🔐 **Role-Based Security**
- **Admin Role** - Full system access (upload, delete, chat, settings)
- **User Role** - Chat-only access with document queries
- **JWT Authentication** - Secure token-based access control
- **Session Management** - Automatic token refresh and expiration
- **Input Validation** - Prompt guardrails and security filters

### 🎨 **Modern UI/UX Design**
- **Responsive Design** - Works perfectly on desktop and mobile
- **Real-time Typing Effects** - Animated response display
- **Glassmorphism Effects** - Modern visual design with backdrop blur
- **Gradient Themes** - Professional color schemes
- **Hover Animations** - Interactive elements with smooth transitions
- **Loading States** - Clear feedback during operations

---

## 🔄 **System Workflows & Architecture**

### 📋 **1. Document Upload & Processing Workflow**
```
User Uploads Document → File Validation → Document Parsing → Text Chunking → 
Vector Embeddings → Qdrant Storage → Metadata Database → UI Update
```

**Detailed Steps:**
1. **File Upload** - Admin drags/drops or selects files
2. **Validation** - Check file type, size, and format
3. **Parsing** - Extract text from PDF, DOCX, PPTX, XLSX, TXT
4. **Chunking** - Split text into semantic chunks (overlap for context)
5. **Embedding** - Generate vector embeddings using sentence-transformers
6. **Storage** - Store vectors in Qdrant with metadata (file_id, chunk_id)
7. **Database** - Update file metadata and status
8. **UI Feedback** - Show upload progress and completion

### 💬 **2. Contextual Chat Workflow**
```
User Question → Session Check → Context Retrieval → Vector Search → 
Document Chunks → Context Assembly → AI Processing → Response Generation → 
Context Update → UI Display
```

**Detailed Steps:**
1. **Question Input** - User types question in chat interface
2. **Session Management** - Generate/retrieve unique session ID
3. **Context Retrieval** - Get last 6-10 messages from conversation history
4. **Vector Search** - Query Qdrant for relevant document chunks
5. **Context Assembly** - Combine conversation history + document context
6. **AI Processing** - Send to Claude AI with full context
7. **Response Generation** - AI generates contextual response
8. **Context Update** - Add new Q&A to conversation history
9. **UI Display** - Show response with typing animation

### 🔐 **3. Authentication & Authorization Workflow**
```
Login Request → Credential Validation → JWT Generation → Role Assignment → 
UI Routing → Permission Enforcement → Session Management
```

**Detailed Steps:**
1. **Login** - User enters username/password
2. **Validation** - Check credentials against database
3. **JWT Creation** - Generate secure token with user info and role
4. **Role Assignment** - Determine admin vs user permissions
5. **UI Routing** - Redirect to appropriate interface
6. **Permission Enforcement** - Backend validates JWT on each request
7. **Session Management** - Handle token refresh and expiration

### 🗑️ **4. File Deletion Workflow**
```
Delete Request → Permission Check → Vector Cleanup → Database Update → 
Cache Invalidation → UI Refresh
```

**Detailed Steps:**
1. **Delete Request** - Admin clicks delete on file card
2. **Permission Check** - Verify admin role and authorization
3. **Vector Cleanup** - Remove all document chunks from Qdrant by file_id
4. **Database Update** - Remove file metadata from database
5. **Cache Invalidation** - Clear any cached responses for that file
6. **UI Refresh** - Update file list and show confirmation

---

## 🛠️ **Technical Implementation Details**

### 🧠 **Context Management System**
```javascript
// Frontend: Session & Context Tracking
const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
const [messages, setMessages] = useState([]);

// Context sent with each request
const conversationHistory = messages.slice(-10).map(msg => ({
  role: msg.user ? "user" : "assistant",
  content: msg.text,
  timestamp: msg.timestamp
}));
```

```python
# Backend: Context Processing
def answer_with_context(self, query: str, conversation_history: List, top_k: int = 5):
    # Combine document chunks + conversation context
    conversation_context = "\n\nPrevious Conversation:\n"
    for msg in conversation_history[-6:]:
        role = "Human" if msg.role == "user" else "Assistant"
        conversation_context += f"{role}: {msg.content}\n"
    
    # Send to AI with full context
    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}{conversation_context}\nCurrent Question: {query}"
```

### 🔍 **Vector Search & RAG Pipeline**
```python
# Document Processing Pipeline
def process_document(file_path: str, file_id: str):
    # 1. Parse document
    text = extract_text(file_path)
    
    # 2. Create chunks with overlap
    chunks = create_chunks(text, chunk_size=500, overlap=50)
    
    # 3. Generate embeddings
    embeddings = sentence_transformer.encode(chunks)
    
    # 4. Store in Qdrant
    points = [
        PointStruct(
            id=f"{file_id}_{i}",
            vector=embedding.tolist(),
            payload={"text": chunk, "file_id": file_id}
        ) for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    qdrant_client.upsert(collection_name="kb_docs", points=points)
```

### 🔐 **Security & Authentication**
```python
# JWT Token with Role Information
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Role-based Permission Enforcement
@router.post("/files/upload")
async def upload_file(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
```

### 🎨 **Modern UI Components**
```javascript
// Real-time Typing Animation
const typeMessage = (text, callback) => {
  let index = 0;
  const interval = setInterval(() => {
    setTypingText(text.substring(0, index));
    index++;
    if (index > text.length) {
      clearInterval(interval);
      callback();
    }
  }, 30);
};

// Context-aware Message Display
{messages.map((m, i) => (
  <div className={`message ${m.user ? "user" : "bot"}`}>
    <div className="message-content">{m.text}</div>
    <div className="message-actions">
      <button onClick={() => deleteMessage(i)}>🗑️</button>
      <button onClick={() => deleteFromIndex(i)}>✂️</button>
    </div>
  </div>
))}
```

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  FastAPI Backend │    │  Vector Database │
│                 │    │                 │    │    (Qdrant)     │
│ • Chat Interface│◄──►│ • RAG Pipeline  │◄──►│ • Document      │
│ • File Upload   │    │ • Context Mgmt  │    │   Embeddings    │
│ • Admin Panel   │    │ • Authentication│    │ • Semantic      │
│ • Session Mgmt  │    │ • File Processing│    │   Search        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                ▲
                                │
                       ┌─────────────────┐
                       │   Claude AI     │
                       │ • Text Generation│
                       │ • Context Aware │
                       │ • Natural Lang. │
                       └─────────────────┘
```

---

## 📁 Project Structure

```
chatbot_rag_system/
├── chatbot_frontend/          # React.js Frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── AdminDashboard.js
│   │   │   ├── ChatWindow.js
│   │   │   ├── FileUploader.js
│   │   │   └── Login.js
│   │   ├── api/              # API integration
│   │   └── styles.css        # Modern styling
│   └── package.json
│
├── chatbot_backend/          # FastAPI Backend
│   ├── app/
│   │   ├── api/              # API routes
│   │   │   ├── routes_auth.py
│   │   │   ├── routes_chat.py  # Context-aware chat
│   │   │   └── routes_files.py
│   │   ├── core/             # Core logic
│   │   │   ├── rag.py        # RAG pipeline
│   │   │   ├── vectorstore.py
│   │   │   └── vector_singleton.py
│   │   └── models/           # Data models
│   └── requirements.txt
│
├── .env                      # Environment variables (gitignored)
└── README.md                # This file
```

---

## 🛠️ Setup Instructions

### Prerequisites
- **Node.js 16+** (for frontend)
- **Python 3.10** (for backend)
- **Docker** (for Qdrant vector database)
- **Claude API Key** (from Anthropic)

### 1. Clone Repository
```bash
git clone <repository-url>
cd chatbot_rag_system
```

### 2. Backend Setup
```bash
cd chatbot_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your Claude API key and other settings
```

### 3. Frontend Setup
```bash
cd chatbot_frontend

# Install dependencies
npm install

# Start development server
npm start
```

### 4. Start Vector Database
```bash
# Start Qdrant vector database
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

### 5. Start Backend
```bash
cd chatbot_backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔧 Environment Configuration

Create a `.env` file in the backend directory:

```env
# Claude AI Configuration
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_API_URL=https://api.anthropic.com/v1/messages
CLAUDE_MODEL=claude-3-haiku-20240307
CLAUDE_MAX_TOKENS=1000
CLAUDE_TEMPERATURE=0.0

# Custom System Prompt (optional - uses default if empty)
SYSTEM_PROMPT=

# Vector Database
VECTOR_DB_URL=http://localhost:6333
VECTOR_DB_FALLBACK=true

# Authentication
SECRET_KEY=your-super-secret-jwt-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Upload Settings
MAX_FILE_SIZE_MB=25
ALLOWED_FILE_TYPES=pdf,docx,pptx,xlsx,txt
UPLOAD_DIR=uploads

# Server Settings
HOST=0.0.0.0
PORT=8000
DEBUG=false
RELOAD=false

# CORS Settings (Production)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_HEADERS=*

# Optional: Redis Cache
USE_REDIS=false
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TIMEOUT=5

# Activity Tracking
ACTIVITY_LOG_DIR=activity_logs
ACTIVITY_RETENTION_DAYS=30
```

### **Production Configuration Notes**

1. **CORS Origins**: Replace `*` with your actual frontend domain
2. **SECRET_KEY**: Use a strong, random key (32+ characters)
3. **DEBUG**: Always set to `false` in production
4. **RELOAD**: Set to `false` in production
5. **HOST**: Use `0.0.0.0` to bind to all interfaces
6. **SYSTEM_PROMPT**: Customize the AI assistant's behavior

---

## 📊 **Development Journey & Achievements**

### 🎯 **Major Milestones Completed**

#### **Phase 1: Core RAG System** ✅
- ✅ Document upload and processing (PDF, DOCX, PPTX, XLSX, TXT)
- ✅ Vector embeddings with sentence-transformers
- ✅ Qdrant vector database integration
- ✅ Basic chat functionality with Claude AI
- ✅ JWT authentication system

#### **Phase 2: Advanced Features** ✅
- ✅ **Conversation Context Management** - Session-based chat history
- ✅ **Role-based Access Control** - Admin/User separation
- ✅ **Modern UI Design** - Glassmorphism and gradient themes
- ✅ **Real-time Typing Effects** - Animated response display
- ✅ **Message Management** - Delete individual messages or segments

#### **Phase 3: Production Readiness** ✅
- ✅ **Error Handling** - Comprehensive exception management
- ✅ **Logging System** - Detailed debugging and monitoring
- ✅ **Security Enhancements** - Input validation and prompt guards
- ✅ **Performance Optimization** - Vector singleton pattern
- ✅ **File Management** - Proper deletion with vector cleanup

### 🔧 **Critical Bug Fixes Resolved**
1. **Vector Store Singleton** - Fixed document visibility across operations
2. **Qdrant Collection Management** - Prevented data loss on uploads
3. **Authentication Flow** - Fixed OAuth2 format and JWT handling
4. **Context Processing** - Resolved Pydantic object handling
5. **File Deletion** - Fixed Qdrant filter format for proper cleanup

### 🚀 **Performance & Scalability**
- **Vector Search**: Sub-second response times with Qdrant
- **Context Management**: Optimized to use last 6-10 messages
- **Memory Efficiency**: Proper cleanup and garbage collection
- **Concurrent Users**: JWT-based stateless authentication
- **File Processing**: Chunked processing for large documents

---

## 🎯 Usage

### Default Credentials
- **Admin**: `admin` / `admin123` (full access)
- **User**: `user` / `user123` (chat only)

### Admin Features
1. **Upload Documents** - Add files to the knowledge base
2. **File Management** - View, download, delete, and organize documents
3. **Chat Interface** - Ask questions about uploaded content
4. **Activity Feed** - Monitor all system activities and user interactions
5. **System Settings** - Manage passwords and view analytics
6. **System Reset** - Complete data reset with safety confirmations (admin only)

### User Features
1. **Chat Interface** - Ask questions about available documents
2. **Context Management** - Natural follow-up conversations
3. **Message Controls** - Delete messages or conversation segments

### Context Management
- **Session-Based**: Each chat session maintains its own context
- **Natural Flow**: Ask follow-up questions without repeating context
- **Message History**: Last 10 messages included in context
- **Session Reset**: Start fresh conversations anytime

### System Reset Features
- **Reset All Files**: Delete all uploaded documents and vector embeddings
- **Reset Everything**: Complete system reset including activities, cache, and vector database
- **Safety Confirmations**: Multiple confirmation dialogs to prevent accidental resets
- **Activity Logging**: All reset operations are logged for audit purposes
- **Admin Only**: Reset functionality restricted to admin users only

---

## 🚀 Deployment

### Frontend (Netlify/Vercel)
```bash
cd chatbot_frontend
npm run build
# Deploy dist/ folder
```

### Backend (Railway/Heroku)
```bash
cd chatbot_backend
# Set environment variables in platform
# Deploy with Python 3.10 runtime
```

### Vector Database
- Use Qdrant Cloud for production
- Update `VECTOR_DB_URL` in environment

---

## 🔍 API Endpoints

### Authentication
- `POST /auth/token` - Login and get JWT token

### File Management
- `POST /files/upload` - Upload document
- `GET /files/list` - List all files
- `GET /files/download/{file_id}` - Download original file
- `GET /files/metadata/{file_id}` - Get file metadata
- `DELETE /files/{file_id}` - Delete file
- `DELETE /files/reset-all` - Reset all files (admin only)

### Activity Tracking
- `GET /activity/recent` - Get recent activities
- `GET /activity/by-type/{activity_type}` - Get activities by type
- `GET /activity/by-user/{username}` - Get activities by user (admin only)
- `GET /activity/my-activities` - Get current user's activities
- `GET /activity/stats` - Get activity statistics
- `GET /activity/summary` - Get comprehensive activity summary
- `DELETE /activity/cleanup` - Cleanup old activities (admin only)
- `DELETE /activity/reset-all` - Reset everything (admin only)

### Chat with Context
- `POST /chat/ask` - Ask question with optional context
  ```json
  {
    "question": "Your question here",
    "session_id": "unique_session_id",
    "maintain_context": true,
    "conversation_history": [
      {"role": "user", "content": "Previous question"},
      {"role": "assistant", "content": "Previous response"}
    ]
  }
  ```

---

## 🛡️ Security Features

- **JWT Authentication** - Secure token-based access
- **Role-Based Access** - Admin vs user permissions
- **Input Validation** - Prompt guardrails and sanitization
- **File Type Validation** - Only allowed file types accepted
- **Size Limits** - Configurable file size restrictions

---

## 🎨 UI Features

- **Modern Design** - Clean, professional interface
- **Responsive Layout** - Works on desktop and mobile
- **Real-time Typing** - Animated response display
- **Context Indicators** - Shows conversation state
- **Message Actions** - Delete, edit, and manage messages
- **File Cards** - Beautiful document display
- **Admin Dashboard** - Comprehensive management interface

---

## 📁 **Project Structure**

### **Backend Structure** (`chatbot_backend/`)

```
chatbot_backend/
├── app/
│   ├── api/                    # API Routes
│   │   ├── routes_auth.py      # Authentication endpoints (login, password change)
│   │   ├── routes_files.py     # File management (upload, download, delete, list)
│   │   ├── routes_chat.py      # Chat endpoints (ask questions, context management)
│   │   ├── routes_health.py    # System health monitoring
│   │   └── routes_activity.py  # Activity tracking endpoints
│   ├── core/                   # Core System Components
│   │   ├── auth.py            # JWT authentication & password hashing
│   │   ├── cache.py           # Redis cache management
│   │   ├── database.py        # Database connection & initialization
│   │   ├── embeddings.py      # Text embedding generation
│   │   ├── rag.py             # RAG pipeline with configurable prompts
│   │   ├── vector_singleton.py # Vector store singleton pattern
│   │   └── vectorstore.py     # Vector database operations
│   ├── models/                 # Database Models
│   │   ├── base.py            # SQLAlchemy base model
│   │   ├── chat_tracking.py   # Chat session tracking model
│   │   ├── file_metadata.py   # File metadata model
│   │   ├── file.py            # File model
│   │   └── user.py            # User model
│   ├── services/               # Business Logic Services
│   │   ├── activity_tracker.py # Activity logging & tracking
│   │   ├── chat_tracking.py   # Chat session management
│   │   ├── file_storage.py    # File storage operations
│   │   └── health_monitor.py  # System health monitoring
│   ├── utils/                  # Utility Functions
│   │   ├── file_parser.py     # Document parsing (PDF, DOCX, etc.)
│   │   └── prompt_guard.py    # Input validation & security
│   ├── config.py              # Configuration management
│   └── main.py                # FastAPI application setup
├── uploads/                    # File Storage Directory
├── activity_logs/              # Activity Tracking Storage
├── chatbot.db                  # SQLite Database
├── requirements.txt            # Python Dependencies
└── start_server.py            # Server startup script
```

### **Frontend Structure** (`chatbot_frontend/`)

```
chatbot_frontend/
├── public/
│   └── index.html             # Main HTML template
├── src/
│   ├── api/
│   │   └── api.js             # API client configuration
│   ├── components/             # React Components
│   │   ├── ActivityFeed.js    # Activity tracking display
│   │   ├── AdminDashboard.js  # Main admin interface
│   │   ├── AdminSettings.js   # Settings & password management
│   │   ├── ChatWindow.js      # Chat interface
│   │   ├── FileUploader.js    # File upload & management
│   │   └── Login.js           # Authentication form
│   ├── App.js                 # Main application component
│   ├── index.js               # Application entry point
│   ├── index.css              # Global styles
│   └── styles.css             # Component styles
├── package.json               # Node.js dependencies
└── README.md                  # Frontend documentation
```

### **Key Files Explained**

#### **Backend Core Files**
- **`app/main.py`**: FastAPI application with CORS, routing, and middleware
- **`app/config.py`**: Environment-based configuration with production-ready defaults
- **`app/core/rag.py`**: RAG pipeline with configurable system prompts
- **`app/services/activity_tracker.py`**: Local JSON-based activity tracking
- **`app/api/routes_*.py`**: RESTful API endpoints for all features

#### **Frontend Core Files**
- **`src/App.js`**: Main application routing and authentication state
- **`src/components/AdminDashboard.js`**: Comprehensive admin interface
- **`src/components/ActivityFeed.js`**: Real-time activity monitoring
- **`src/api/api.js`**: HTTP client with authentication headers

#### **Configuration Files**
- **`.env`**: Environment variables (API keys, database URLs, etc.)
- **`requirements.txt`**: Python package dependencies
- **`package.json`**: Node.js package dependencies

---

## 🔧 Development

### Frontend Development
```bash
cd chatbot_frontend
npm start  # Development server on :3000
npm test   # Run tests
npm run build  # Production build
```

### Backend Development
```bash
cd chatbot_backend
uvicorn app.main:app --reload  # Development server on :8000
pytest tests/  # Run tests
```

### Adding New Features
1. **Frontend**: Add components in `src/components/`
2. **Backend**: Add routes in `app/api/`
3. **Models**: Update Pydantic models for new data structures
4. **Context**: Modify RAG pipeline for enhanced context handling

---

## 📝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support

For issues and questions:
1. Check the troubleshooting sections in backend/frontend READMEs
2. Review API documentation at `http://localhost:8000/docs`
3. Open an issue on GitHub

---

**Built with ❤️ using React, FastAPI, Qdrant, and Claude AI**
