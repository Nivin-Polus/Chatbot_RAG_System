# 🤖 Collection-Based RAG Chatbot System

A **production-ready Collection-Based Retrieval-Augmented Generation (RAG) chatbot system** with light theme design, horizontal layout, and comprehensive collection management. The system uses a single vector database divided into collections, each with dedicated admins, users, custom prompts, and unique identifiers. Built with React frontend and FastAPI backend for scalable AI-powered conversations.

## 🚀 System Architecture

This **collection-based** RAG chatbot system uses a single vector database intelligently divided into collections. Each collection operates as an independent unit with:

- **Unique Collection ID**: Every collection has a distinct identifier
- **Dedicated Admin**: Each collection has one admin with full management rights
- **Collection Users**: Multiple users can be assigned to each collection
- **Custom Prompts**: Each collection has its own AI prompt configuration
- **Website Integration**: Optional website URL assignment per collection
- **Isolated Data**: Complete separation between collections

## 🎯 Key Features

### 📚 **Collection-Based Architecture**
- **Single Vector Database**: One shared database divided into logical collections
- **Collection Management**: Super admin can create and manage all collections
- **Unique Identifiers**: Each collection has a unique ID for precise management
- **Website URLs**: Collections can be linked to specific websites
- **Admin Assignment**: Each collection has a dedicated admin user

### 🤖 **Custom Prompt Management**
- **Collection-Specific Prompts**: Each collection has its own AI prompt configuration
- **Database-Driven Prompts**: All prompts stored and managed in database
- **Prompt Templates**: System prompt, user prompt, and context templates
- **AI Model Configuration**: Per-prompt model settings (Claude variants, tokens, temperature)
- **Default Prompt System**: Each collection can have a default prompt
- **Prompt Testing**: Built-in functionality to test prompts before deployment

### 🔐 **Role-Based Access Control**
- **Super Admin**: Global system management and collection oversight
  - Create and manage all collections
  - View and edit all prompts across collections
  - Assign admins and users to collections
  - System-wide analytics and monitoring
- **Collection Admin**: Collection-scoped administration
  - View and edit their collection's default prompt
  - Manage users within their collection
  - Upload and manage files for their collection
  - Collection-specific analytics
- **Collection User**: Limited access within assigned collection
  - Access chat interface with collection-specific data
  - Use collection's configured prompts
  - View only files they have permission for

### 📁 **Multi-Tenant Document Management**
- **Department-Scoped Files**: Each department has isolated file storage
- **Granular Access Control**: File-level permissions with read/download/delete rights
- **File Access Management**: Grant, revoke, and manage user file permissions
- **Quota Enforcement**: Per-department limits on file count and storage size
- **Multi-format Support**: PDF, DOCX, PPTX, XLSX, TXT with metadata extraction
- **Public/Private Files**: Department-wide or user-specific file visibility
- **Expiration Support**: Time-limited file access with automatic revocation
- **MySQL Database**: Production-ready storage with connection pooling

### 🧠 **Multi-Tenant RAG Pipeline**
- **Tenant-Isolated Vector Search**: Single Qdrant collection with metadata filtering
- **Automatic Embedding Generation**: Sentence Transformers (all-MiniLM-L6-v2)
- **Access-Controlled Retrieval**: Only searches user's accessible files
- **Department Boundaries**: Strict isolation prevents cross-tenant data access
- **Claude AI Integration**: Haiku model for natural language responses
- **Context-Aware Conversations**: Maintains chat history within tenant boundaries
- **Efficient Metadata Filtering**: website_id, file_id, and user permissions

### 💬 **Chat Interface**
- Real-time typing animations (30ms character intervals)
- Conversation context maintenance with session tracking
- Session-based chat history with unique session IDs
- Message management (delete individual messages or segments)
- Auto-scrolling and responsive design
- **Modern Tabbed Interface**: File Management, Chat, Settings

### 📊 **Multi-Tenant Analytics & Monitoring**
- **Department-Level Analytics**: Usage statistics per website/department
- **Query Logging**: Comprehensive tracking of all user interactions
- **Usage Monitoring**: File access patterns, user activity, and performance metrics
- **Quota Tracking**: Real-time monitoring of department resource usage
- **Admin Dashboards**: Super admin (global) and user admin (department) views
- **Audit Trails**: Complete logging of administrative actions and file access
- **Performance Analytics**: Response times, token usage, and system health

### 🎨 **Light Bootstrap Dashboard Design**
- **Light Bootstrap Inspired**: Modern orange gradient theme with professional styling
- **Collapsible Sidebar**: Responsive navigation with icons and labels
- **Card-Based Layout**: Clean card design for data presentation
- **Gradient Themes**: Orange-to-amber gradient scheme with modern shadows
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Smooth Animations**: Hover effects, transitions, and loading states
- **Statistics Cards**: Beautiful overview cards with icons and metrics
- **Modern Navigation**: Sidebar with role-based menu items

### 🔧 **System Architecture & Flexibility**
- **Database-Optional Architecture**: Runs without SQLAlchemy installation
- **Automatic Fallbacks**: In-memory vector storage, JSON file persistence
- **Flexible Configuration**: Supports multiple environment variable formats
- **Health Monitoring**: Built-in diagnostics for all system components
- **Progressive Enhancement**: Start minimal, add features as needed
- **Production-Ready**: Comprehensive error handling and logging
- **Loading States** - Clear feedback during operations

---

## 🎨 **Light Theme Design**

### 🌟 **Modern Light Theme Interface**
- **Light Color Palette**: Soft blues, gentle gradients, and clean whites
- **Horizontal Layout**: Statistics cards arranged horizontally for better space utilization
- **Inter Font**: Modern, clean typography for enhanced readability
- **Subtle Shadows**: Gentle depth effects for professional appearance
- **Responsive Design**: Adapts beautifully to all screen sizes

### 📊 **Dashboard Features**
- **Collapsible Sidebar**: Clean navigation with role-based menu items
- **Statistics Overview**: Horizontal stat cards showing key metrics
- **Card-Based Layout**: Clean card design for all data presentation
- **Smooth Animations**: Subtle hover effects and transitions
- **Professional Styling**: Light Bootstrap inspired design elements

## 🔧 **System Workflow**

### 👑 **Super Admin Capabilities**
1. **Collection Management**: Create new collections with unique IDs
2. **Admin Assignment**: Assign dedicated admins to each collection
3. **User Management**: Add users to specific collections
4. **Prompt Oversight**: View and edit all prompts across all collections
5. **Website Integration**: Assign website URLs to collections
6. **Global Analytics**: Monitor system-wide statistics and performance

### 🛠️ **Collection Admin Capabilities**
1. **Prompt Management**: View and edit their collection's default prompt
2. **User Management**: Manage users within their assigned collection
3. **File Management**: Upload and organize collection-specific documents
4. **Website Configuration**: Manage their collection's website URL
5. **Collection Analytics**: Monitor collection-specific metrics and usage

---

## 🏗️ **Collection-Based System Architecture**

### 🎯 **Architecture Overview**

The system implements a **collection-based approach** using:
- **Single Qdrant Vector Database**: One shared database logically divided into collections
- **Collection-Based Filtering**: Metadata filtering ensures complete collection isolation
- **MySQL Database**: Stores collection metadata, user assignments, and prompt configurations
- **Role-Based Access Control**: Super Admin, Collection Admin, and Collection User roles
- **Unique Collection IDs**: Each collection has a distinct identifier for precise management

### 👥 **User Roles & Permissions**

| Role | Scope | Permissions | Default Account |
|------|-------|-------------|-----------------|
| **Super Admin** | Global | Create collections, manage all prompts, assign admins | `superadmin/superadmin123` |
| **Collection Admin** | Collection | Manage collection prompt, users, and files | `admin/admin123` |
| **Collection User** | Collection | Access collection chat, use assigned prompt | `user/user123` |

### 🗄️ **Database Schema**

#### Core Collection Tables
- **`collections`** - Collection definitions with unique IDs and website URLs
- **`users`** - Enhanced with collection_id and role-based permissions
- **`prompts`** - AI prompts scoped to collections with model configurations
- **`file_metadata`** - Files scoped to collections with access control
- **`collection_users`** - User assignments to collections with role management
- **`query_logs`** - Usage tracking and analytics per collection

### 🔍 **Vector Database Strategy**

```python
# Single Qdrant database with collection-based filtering
search_filter = Filter(
    must=[
        FieldCondition(key="collection_id", match=MatchValue(value=user_collection_id)),
        FieldCondition(key="file_id", match=MatchValue(value=accessible_file_ids))
    ]
)
```

**Benefits:**
- **Single Infrastructure** - One Qdrant instance for all collections
- **Strict Isolation** - Metadata filters prevent cross-collection access
- **Scalable** - Efficient indexing and querying
- **Cost-Effective** - Shared resources with logical separation

---

## 🚀 **Quick Start Guide**

### 📋 **Prerequisites**
- Python 3.8+
- Node.js 16+
- MySQL 8.0+
- Qdrant vector database
- Claude API key (Anthropic)

### 🔧 **Installation Steps**

1. **Clone Repository**
```bash
git clone <repository-url>
cd Chatbot_RAG_System_UI_1
```

2. **Backend Setup**
```bash
cd chatbot_backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database credentials and API keys
python setup_mysql.py
python -m uvicorn app.main:app --reload
```

3. **Frontend Setup**
```bash
cd chatbot_frontend
npm install
npm start
```

4. **Access the System**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### 🔑 **Default Login Credentials**
- **Super Admin**: `superadmin` / `superadmin123`
- **Collection Admin**: `admin` / `admin123`
- **Collection User**: `user` / `user123`

---

## 📁 **File Structure**

```
Chatbot_RAG_System_UI_1/
├── chatbot_backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── core/             # Core functionality
│   │   ├── models/           # Database models
│   │   └── main.py           # Application entry point
│   ├── requirements.txt      # Python dependencies
│   └── .env.example         # Environment variables template
├── chatbot_frontend/         # React frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── api/             # API client
│   │   └── App.js           # Main application
│   ├── package.json         # Node dependencies
│   └── public/              # Static assets
└── README.md                # This file
```

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

## 🚀 **Quick Multi-Tenant Setup**

### 🎯 **Instant Setup (5 Minutes)**

1. **Clone and Setup Backend**
   ```bash
   git clone <repository-url>
   cd chatbot_backend
   pip install -r requirements.txt
   cp .env.example .env
   # Add your Claude API key to .env
   ```

2. **Start Multi-Tenant System**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

3. **Access Default Accounts**
   - **Super Admin**: `superadmin/superadmin123` (manage all departments)
   - **User Admin**: `admin/admin123` (manage Default Organization)
   - **Regular User**: `user/user123` (limited file access)

4. **Create Your First Department**
   - Login as Super Admin
   - Create new website/department
   - Add User Admin for the department
   - Start uploading department-specific files

### 🏢 **Multi-Tenant Workflow**

1. **Super Admin** creates departments and assigns User Admins
2. **User Admins** manage their department users and files
3. **Users** access only their granted files within their department
4. **Complete Isolation** - departments cannot see each other's data

---

## 🛠️ Setup Instructions

### 📋 Prerequisites

### **Minimal Setup (Recommended)**
- **Python 3.8+**
- **Node.js 16+** and **npm**
- **Claude API Key** (from Anthropic)

### **Full Setup (Optional)**
- **Python 3.8+**
- **Node.js 16+** and **npm**
- **Docker** (for Qdrant vector database)
- **Claude API Key** (from Anthropic)
- **SQLAlchemy** (for database features)

### 1. Clone Repository
```bash
git clone <repository-url>
cd chatbot_rag_system
```

### 2. Backend Setup

#### **Option A: Full Setup (with Database)**
```bash
cd chatbot_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install all dependencies (includes SQLAlchemy, Qdrant, Redis)
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your Claude API key and other settings
```

#### **Option B: Minimal Setup (No Database Required) - RECOMMENDED**
```bash
cd chatbot_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install minimal dependencies (core packages only)
pip install -r requirements-minimal.txt

# Create .env file
cp .env.example .env
# Edit .env with your Claude API key and other settings
```

**🚀 Quick Start:** Use Option B for immediate setup - no database installation required!

#### **📊 Storage Modes Explained**

| Feature | With Database (Option A) | Without Database (Option B) |
|---------|-------------------------|------------------------------|
| **File Metadata** | SQLite database | JSON files in `/storage` |
| **Chat History** | SQLite database | JSON files in `/storage` |
| **Vector Storage** | Qdrant (if available) | In-memory fallback |
| **Persistence** | Full persistence | Files persist, vectors in-memory |
| **Performance** | Better for production | Good for development/testing |
| **Setup Complexity** | More dependencies | Minimal dependencies |
| **Data Recovery** | Full database backup | JSON file backup |

**Recommendation:**
- **Development/Testing**: Use Option B (minimal setup)
- **Production**: Use Option A (full database)

#### **🔐 Critical Security Setup**

**Generate a Secure SECRET_KEY:**
```bash
# Method 1: Using Python
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Method 2: Use provided script (in backend folder)
cd chatbot_backend
python generate_secret.py
```

**Update your .env file with:**
```env
# Replace this with your generated key
SECRET_KEY=your_generated_secure_key_here

# Add your Claude API key
CLAUDE_API_KEY=your_claude_api_key_here
```

**⚠️ Important Security Notes:**
- Never use the default SECRET_KEY in production
- Keep your .env file secret (it's already in .gitignore)
- Generate a new key for each environment (dev/staging/prod)
- Use at least 32 characters for the secret key

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

## 🔧 **Post-Setup Steps & Troubleshooting**

### **After Setting Up .env File:**

1. **Start Backend Server** (New Improved Startup!)
   ```bash
   cd chatbot_backend
   python start_server.py
   ```
   
   **Expected Output:**
   ```
   INFO:__main__:🤖 RAG Chatbot Backend Startup
   INFO:__main__:✅ All required packages are installed
   INFO:__main__:✅ All environment variables are set
   INFO:app.core.database:✅ Database initialized successfully (in-memory mode)
   INFO:__main__:🚀 Starting RAG Chatbot Backend...
   INFO:__main__:📍 Server will be available at: http://0.0.0.0:8000
   ```

2. **Start Frontend Server**
   ```bash
   cd chatbot_frontend
   npm start
   ```

3. **Test Authentication**
   - Login with: `admin/admin123` (full access) or `user/user123` (chat only)
   - System automatically detects missing dependencies and uses fallback storage

### **Common Issues & Solutions:**

| Issue | Cause | Solution |
|-------|-------|----------|
| `Missing dependency: SQLAlchemy` | Database packages not installed | Use `pip install -r requirements-minimal.txt` |
| `401 Unauthorized` | Invalid/missing SECRET_KEY | Generate new SECRET_KEY, restart server |
| `404 Not Found` | Server not running | Start backend server first |
| `CORS errors` | Frontend/backend mismatch | Check both servers are running |
| `Reset functionality fails` | Outdated server | Restart backend to load latest routes |
| `Environment variables not found` | .env file not loaded | Ensure .env file is in chatbot_backend folder |

### **🆕 New Features & Improvements:**

#### **Database-Optional Architecture**
- **Automatic Fallback**: System detects missing SQLAlchemy and uses JSON file storage
- **In-Memory Vector Storage**: Works without Qdrant installation
- **Persistent File Metadata**: Stored in `/storage` directory as JSON files
- **Zero Database Setup**: Run immediately with minimal dependencies

#### **Enhanced Startup Process**
- **Smart Environment Detection**: Automatically loads .env file and validates settings
- **Improved Error Messages**: Clear feedback on missing dependencies or configuration
- **Flexible Host/Port Configuration**: Supports both SERVER_HOST/SERVER_PORT and HOST/PORT
- **Health Monitoring**: Built-in system health checks and diagnostics

#### **Production-Ready Features**
- **Role-Based Access Control**: Admin (full access) vs User (chat only) interfaces
- **Modern UI Design**: Glassmorphism effects, gradient themes, responsive design
- **Conversation Context**: Maintains chat history across sessions
- **File Management**: Drag-drop upload, metadata tracking, organized storage
- **Activity Tracking**: Real-time monitoring with filtering and statistics
- **Reset Functionality**: Complete system reset with vector database cleanup

#### **Flexible Dependency Management**
- **`requirements.txt`**: Full setup with all optional dependencies (SQLAlchemy, Qdrant, Redis)
- **`requirements-minimal.txt`**: Minimal setup with only core dependencies (FastAPI, Claude AI, etc.)
- **Automatic Detection**: System automatically detects missing packages and provides fallbacks
- **Progressive Enhancement**: Start minimal, add features as needed

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

# Multi-Tenant Configuration
DEFAULT_WEBSITE_NAME="Your Organization"
DEFAULT_WEBSITE_DOMAIN="yourdomain.com"
DEFAULT_MAX_USERS_PER_WEBSITE=100
DEFAULT_MAX_FILES_PER_WEBSITE=1000
DEFAULT_MAX_STORAGE_MB_PER_WEBSITE=10240

# MySQL Database (Required for Multi-Tenant)
DATABASE_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=chatbot_rag
DATABASE_USER=your_mysql_user
DATABASE_PASSWORD=your_mysql_password
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
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
- `POST /auth/token` - Login and get JWT token with role and tenant information

### Multi-Tenant Website Management
- `GET /websites/` - List websites (filtered by permissions)
- `GET /websites/{website_id}` - Get website details with usage statistics
- `POST /websites/` - Create new website/department (super admin only)
- `PUT /websites/{website_id}` - Update website settings
- `DELETE /websites/{website_id}` - Delete website (super admin only)
- `GET /websites/{website_id}/analytics` - Get department analytics

### Multi-Tenant User Management
- `GET /users/me` - Get current user info with permissions
- `GET /users/` - List users (filtered by permissions)
- `GET /users/{user_id}` - Get user details
- `POST /users/` - Create user with role and website assignment
- `PUT /users/{user_id}` - Update user information
- `DELETE /users/{user_id}` - Deactivate user
- `POST /users/{user_id}/activate` - Activate user
- `GET /users/{user_id}/accessible-files` - Get user's accessible files

### Multi-Tenant File Management
- `POST /files/upload` - Upload document with website and access control
- `GET /files/list` - List accessible files (filtered by permissions)
- `GET /files/download/{file_id}` - Download file (permission-checked)
- `GET /files/metadata/{file_id}` - Get file metadata
- `DELETE /files/{file_id}` - Delete file (permission-checked)
- `POST /files/{file_id}/access` - Grant file access to user
- `PUT /files/{file_id}/access/{access_id}` - Update file access permissions
- `DELETE /files/{file_id}/access/{access_id}` - Revoke file access
- `GET /files/{file_id}/access` - List file access permissions

### Activity Tracking
- `GET /activity/recent` - Get recent activities (tenant-filtered)
- `GET /activity/by-type/{activity_type}` - Get activities by type
- `GET /activity/by-user/{username}` - Get activities by user (admin only)
- `GET /activity/my-activities` - Get current user's activities
- `GET /activity/stats` - Get activity statistics (tenant-scoped)

### Multi-Tenant Chat
- `POST /chat/ask` - Ask question with tenant and access control
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
  *Note: Only searches files accessible to the user within their department*

---

## 🛡️ Multi-Tenant Security Features

### 🔐 **Authentication & Authorization**
- **JWT Tokens** - Include user role, website_id, and permissions
- **Three-Tier Role System** - Super Admin, User Admin, Regular User
- **Department Isolation** - Complete data separation between tenants
- **Granular Permissions** - File-level access control with expiration

### 🛡️ **Data Protection**
- **Row-Level Security** - All database queries filtered by website_id
- **Vector Store Isolation** - Metadata filtering prevents cross-tenant access
- **File Access Control** - Explicit permission grants required
- **Audit Logging** - Complete trail of all administrative actions

### 🔒 **Access Control**
- **Quota Management** - Per-department limits on users, files, storage
- **Permission Validation** - Every API call validates tenant access
- **Secure File Storage** - Department-scoped file organization
- **Input Validation** - Comprehensive sanitization and validation

### 🚨 **Monitoring & Compliance**
- **Usage Analytics** - Per-tenant monitoring and reporting
- **Query Logging** - Track all user interactions and file access
- **Performance Monitoring** - Response times and system health per tenant
- **Compliance Ready** - Audit trails and data isolation for regulatory requirements

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

## 📚 **Additional Documentation**

### 🏢 **Multi-Tenant System Guide**
- **Complete Setup Guide**: `MULTITENANT_SYSTEM_GUIDE.md`
- **Database Schema**: Detailed table structures and relationships
- **API Reference**: All multi-tenant endpoints with examples
- **Security Guide**: Access control and permission management
- **Troubleshooting**: Common issues and solutions

### 🔧 **Technical Documentation**
- **MySQL Migration Guide**: `MYSQL_MIGRATION_GUIDE.md`
- **Vector Store Architecture**: Metadata filtering strategies
- **Role-Based Access Control**: Implementation details
- **Performance Optimization**: Scaling and monitoring

---

## 🆘 Support

For issues and questions:
1. Check the **Multi-Tenant System Guide** (`MULTITENANT_SYSTEM_GUIDE.md`)
2. Review **MySQL Migration Guide** for database setup
3. Check API documentation at `http://localhost:8000/docs`
4. Review troubleshooting sections in documentation
5. Open an issue on GitHub

---

**Built with ❤️ using React, FastAPI, Qdrant, Claude AI, and MySQL**  
**🏢 Now with Enterprise Multi-Tenant Architecture!**
