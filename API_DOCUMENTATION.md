# API Documentation

This document provides a detailed overview of the backend API endpoints for the Chatbot RAG System.

## Authentication

All API requests (except for public endpoints like health checks and certain auth routes) require a Bearer token for authentication.

### Authorization Header
Include the token in the `Authorization` header of your HTTP requests:
```http
Authorization: Bearer <your_access_token>
```

### User Roles & Permissions
- **Super Admin**: Full access to all websites, users, collections, and system-wide settings.
- **User Admin**: Access to manage a specific website's users, collections, files, and prompts.
- **Regular User**: Access to chat with assigned collections and view accessible files.
- **Plugin User**: Specialized role for programmatic access to specific collections via a static plugin token.

### Obtaining a Token
- **User Login**: Use the `/auth/token` endpoint with username and password to receive an `access_token`.
- **Plugin Users**: Super Admins or User Admins can generate a `plugin_token` via the `/users/{user_id}/plugin-token` endpoint.

---

## Auth API

### 1. User Login (Token Generation)
**Purpose**: Authenticate a user and generate an access token.
**Method**: `POST`
**Endpoint**: `/auth/token`
**Authentication**: None
**Description**: Takes a form-encoded username and password and returns a JWT access token.
**Payload**:
```json
// Content-Type: application/x-www-form-urlencoded
{
  "username": "johndoe",
  "password": "secretpassword"
}
```
**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1...",
  "token_type": "bearer"
}
```

### 2. Verify Token
**Purpose**: Validate the current session token.
**Method**: `GET`
**Endpoint**: `/auth/verify`
**Authentication**: `Bearer <token>` (Required)
**Description**: Checks if the provided token is valid and returns user information.
**Payload**: None
**Response**:
```json
{
  "user_id": "uuid",
  "username": "johndoe",
  "role": "super_admin",
  "website_id": null
}
```

### 3. Change Password
**Purpose**: Update the authenticated user's password.
**Method**: `POST`
**Endpoint**: `/auth/change-password`
**Authentication**: `Bearer <token>` (Required)
**Description**: Updates the password for the currently logged-in user.
**Payload**:
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```
**Response**:
```json
{
  "message": "Password changed successfully"
}
```

### 4. Verify Plugin Token
**Purpose**: Validate a plugin-specific token.
**Method**: `GET`
**Endpoint**: `/auth/plugin-token/verify`
**Authentication**: `Bearer <plugin_token>` (Required)
**Description**: Specialized verification for tokens issued to plugin users.
**Payload**: None
**Response**:
```json
{
  "user_id": "uuid",
  "collection_id": "uuid",
  "is_active": true
}
```

### 5. Get Public Token
**Purpose**: Retrieve a temporary token for public chat access.
**Method**: `GET`
**Endpoint**: `/auth/public/token`
**Authentication**: None
**Description**: Generates a limited-scope token for public-facing chat widgets or unauthenticated users (if enabled).
**Payload**: None
**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1...",
  "token_type": "bearer"
}
```

---

## Activity API

### 1. Get Recent Activities
**Purpose**: Retrieve a list of the most recent system activities.
**Method**: `GET`
**Endpoint**: `/activity/recent`
**Authentication**: `Bearer <token>` (Required)
**Description**: Lists activities with support for pagination and filtering by type, user, or collection.
**Payload**: None (Query Parameters: `limit`, `offset`, `since_hours`, `activity_type`, `username`, `collection_id`)
**Response**:
```json
{
  "activities": [
    {
      "activity_id": "uuid",
      "activity_type": "file_upload",
      "user": "admin",
      "timestamp": "2023-10-27T10:00:00Z",
      "details": { "file_name": "data.pdf" }
    }
  ],
  "count": 1,
  "total": 100,
  "has_more": true
}
```

### 2. Log Activity
**Purpose**: Manually record a custom activity.
**Method**: `POST`
**Endpoint**: `/activity/log`
**Authentication**: `Bearer <token>` (Required)
**Description**: Allows the frontend or other services to log specific events.
**Payload**:
```json
{
  "activity_type": "ui_click",
  "description": "User clicked on settings",
  "collection_id": "optional-uuid",
  "metadata": { "button_id": "save-btn" }
}
```
**Response**:
```json
{
  "status": "logged"
}
```

### 3. Get Activity Statistics
**Purpose**: Retrieve high-level statistics about system activities.
**Method**: `GET`
**Endpoint**: `/activity/stats`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns counts of various activity types over time.
**Payload**: None
**Response**:
```json
{
  "total_activities": 1500,
  "by_type": {
    "file_upload": 120,
    "chat_query": 850
  }
}
```

### 4. System Reset (Emergency)
**Purpose**: Completely clear system data (Files, Vectors, Activities).
**Method**: `DELETE`
**Endpoint**: `/activity/reset-all`
**Authentication**: `Bearer <token>` (Super Admin Required)
**Description**: Destructive action to wipe all user-generated data.
**Payload**: None
**Response**:
```json
{
  "message": "System reset successfully"
}
```

---

## Chat API

### 1. Ask (Authenticated Chat)
**Purpose**: Send a query to the AI assistant using authenticated context.
**Method**: `POST`
**Endpoint**: `/chat/ask`
**Authentication**: `Bearer <token>` (Required)
**Description**: Primary chat endpoint. Conducts a RAG search across accessible documents and generates a response. Supports streaming.
**Payload**:
```json
{
  "question": "How do I reset my password?",
  "collection_id": "uuid",
  "session_id": "optional-uuid",
  "top_k": 5,
  "stream": true,
  "temperature": 0.7
}
```
**Response**:
```json
// If stream=false
{
  "answer": "To reset your password, go to...",
  "sources": [
    { "file_id": "uuid", "file_name": "manual.pdf", "score": 0.85 }
  ],
  "session_id": "uuid"
}

// If stream=true (Server-Sent Events)
// Events: data: {"token": "To"}, data: {"token": " reset"} ... data: {"done": true, "sources": [...]}
```

### 2. Public Ask (Website Widget)
**Purpose**: Allow unauthenticated chat via a public-facing website widget.
**Method**: `POST`
**Endpoint**: `/chat/public/ask`
**Authentication**: None or `Bearer <public_token>` (Depending on config)
**Description**: Limited chat endpoint optimized for public use. Requires `website_url` to identify the context.
**Payload**:
```json
{
  "question": "What are your business hours?",
  "website_url": "https://example.com",
  "session_id": "optional-uuid",
  "stream": false
}
```
**Response**: Same shape as `/chat/ask`.

### 3. Get Chat Sessions
**Purpose**: List all chat sessions for the current user.
**Method**: `GET`
**Endpoint**: `/chat/sessions`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns a list of active and archived chat sessions.
**Payload**: None
**Response**:
```json
[
  {
    "session_id": "uuid",
    "collection_id": "uuid",
    "last_message": "...",
    "updated_at": "2023-10-27T10:00:00Z"
  }
]
```

### 4. Delete Chat Session
**Purpose**: Remove a specific chat session and its history.
**Method**: `DELETE`
**Endpoint**: `/chat/sessions/{session_id}`
**Authentication**: `Bearer <token>` (Required)
**Description**: Permanently deletes a chat session.
**Payload**: None
**Response**:
```json
{
  "message": "Session deleted successfully"
}
```

---

## Collections API (Knowledge Bases)

### 1. List Collections
**Purpose**: Retrieve all collections accessible to the current user.
**Method**: `GET`
**Endpoint**: `/collections/`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns a detailed list of collections, including associated websites and basic metadata.
**Payload**: None
**Response**:
```json
[
  {
    "collection_id": "uuid",
    "name": "Employee Handbook",
    "description": "Internal policy documents",
    "website_id": "uuid",
    "is_active": true,
    "websites": ["https://internal.example.com"]
  }
]
```

### 2. Collection Summary
**Purpose**: Efficiently retrieve a minimal list of collections for selection UI.
**Method**: `GET`
**Endpoint**: `/collections/summary`
**Authentication**: `Bearer <token>` (Required)
**Description**: Lightweight endpoint returning only IDs and Names.
**Payload**: None
**Response**:
```json
[
  {
    "id": "uuid",
    "name": "Employee Handbook"
  }
]
```

### 3. Create Collection
**Purpose**: Provision a new knowledge base.
**Method**: `POST`
**Endpoint**: `/collections/`
**Authentication**: `Bearer <token>` (Super Admin Required)
**Description**: Creates a new collection and optionally initializes its vector database.
**Payload**:
```json
{
  "name": "Product Documentation",
  "description": "Public facing docs",
  "website_url": "https://docs.example.com",
  "website_id": "optional-uuid",
  "admin_email": "admin@example.com"
}
```
**Response**:
```json
{
  "collection_id": "uuid",
  "name": "Product Documentation",
  "status": "created"
}
```

### 4. Get Collection Details
**Purpose**: Retrieve full details of a specific collection.
**Method**: `GET`
**Endpoint**: `/collections/{collection_id}`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns detailed configuration, including user counts and file statistics.
**Payload**: None (Path: `collection_id`)
**Response**:
```json
{
  "collection_id": "uuid",
  "name": "Product Documentation",
  "description": "...",
  "websites": [...],
  "stats": { "file_count": 12, "user_count": 5 }
}
```

---

## Crawler API

### 1. Start Crawl Job
**Purpose**: Initiate a new web crawling process for a specific collection.
**Method**: `POST`
**Endpoint**: `/crawler/start`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Starts an asynchronous crawl of a target URL. Extracted content is automatically indexed into the associated collection.
**Payload**:
```json
{
  "target_url": "https://example.com/docs",
  "collection_id": "uuid",
  "max_pages": 100,
  "max_depth": 3,
  "include_patterns": ["/docs/*"],
  "exclude_patterns": ["*/temp/*"]
}
```
**Response**:
```json
{
  "job_id": "uuid",
  "status": "starting",
  "target_url": "https://example.com/docs"
}
```

### 2. Get Job Status
**Purpose**: Monitor the progress of a specific crawl job.
**Method**: `GET`
**Endpoint**: `/crawler/jobs/{job_id}`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns real-time status and statistics for a given crawl job.
**Payload**: None (Path: `job_id`)
**Response**:
```json
{
  "job_id": "uuid",
  "status": "running",
  "pages_discovered": 150,
  "pages_crawled": 42,
  "start_time": "2023-10-27T10:05:00Z"
}
```

---

## Files API

### 1. Upload Files
**Purpose**: Add new documents to a collection for indexing.
**Method**: `POST`
**Endpoint**: `/files/upload`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Uploads one or more files. Supported formats: PDF, DOCX, TXT.
**Payload**:
```http
// Content-Type: multipart/form-data
files: [binary data]
collection_id: "uuid"
```
**Response**:
```json
{
  "files": [
    { "file_id": "uuid", "file_name": "report.pdf", "status": "processing" }
  ]
}
```

### 2. List Files
**Purpose**: Retrieve a list of all files in a collection.
**Method**: `GET`
**Endpoint**: `/files/list`
**Authentication**: `Bearer <token>` (Required)
**Description**: Lists all uploaded files and crawl jobs within a specific collection.
**Payload**: None (Query Parameter: `collection_id`)
**Response**:
```json
[
  {
    "file_id": "uuid",
    "file_name": "report.pdf",
    "file_type": "pdf",
    "created_at": "2023-10-27T10:00:00Z"
  }
]
```

### 3. File Metadata
**Purpose**: Get detailed information about a specific file.
**Method**: `GET`
**Endpoint**: `/files/metadata/{file_id}`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns metadata such as size, processing status, and uploader info.
**Payload**: None (Path: `file_id`)
**Response**:
```json
{
  "file_id": "uuid",
  "file_name": "report.pdf",
  "status": "completed",
  "size_bytes": 1024560,
  "uploader": "admin"
}
```

---

## Health & Stats API

### 1. Simple Health Check
**Purpose**: Public heartbeat endpoint.
**Method**: `GET`
**Endpoint**: `/health`
**Authentication**: None
**Description**: Returns basic system status (healthy/unhealthy).
**Payload**: None
**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### 2. Detailed System Overview
**Purpose**: Get a comprehensive view of system component health.
**Method**: `GET`
**Endpoint**: `/health/detailed`
**Authentication**: `Bearer <token>` (Required)
**Description**: Checks connectivity to database, vector store, and AI services.
**Payload**: None
**Response**:
```json
{
  "database": "connected",
  "vector_store": "connected",
  "ai_services": "operational",
  "storage_usage": "45%"
}
```

---

## Users API

### 1. Get Current User Profile
**Purpose**: Retrieve information about the authenticated user.
**Method**: `GET`
**Endpoint**: `/users/me`
**Authentication**: `Bearer <token>` (Required)
**Description**: Returns the user's profile, roles, and a list of accessible files.
**Payload**: None
**Response**:
```json
{
  "user_id": "uuid",
  "username": "johndoe",
  "full_name": "John Doe",
  "role": "user_admin",
  "website_id": "uuid",
  "accessible_file_ids": ["uuid1", "uuid2"],
  "can_manage_users": true
}
```

### 2. Create User
**Purpose**: Add a new user to the system.
**Method**: `POST`
**Endpoint**: `/users/`
**Authentication**: `Bearer <token>` (Admin/Super Admin Required)
**Description**: Creates a user and assigns them to specific collections.
**Payload**:
```json
{
  "username": "newuser",
  "password": "securepassword",
  "email": "user@example.com",
  "full_name": "New User",
  "role": "user",
  "website_id": "optional-uuid",
  "collection_ids": ["uuid1"]
}
```
**Response**:
```json
{
  "user_id": "uuid",
  "username": "newuser",
  "status": "created"
}
```

### 3. Generate Plugin Token
**Purpose**: Create a static token for a plugin user.
**Method**: `POST`
**Endpoint**: `/users/{user_id}/plugin-token`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Generates a long-lived Bearer token for third-party plugins.
**Payload**: None
**Response**:
```json
{
  "plugin_token": "plg_eyJhbGciOiJIUzI1..."
}
```

---

## Plugins API

### 1. Register Plugin Integration
**Purpose**: Link a knowledge base to a specific website domain.
**Method**: `POST`
**Endpoint**: `/plugins/integrations`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Creates a new integration for a collection.
**Payload**:
```json
{
  "collection_id": "uuid",
  "website_url": "https://help.acme.com",
  "display_name": "Help Center Bot"
}
```
**Response**:
```json
{
  "id": 1,
  "plugin_username": "help_plugin",
  "plugin_token": "plg_..."
}
```

### 2. Plugin Lookup
**Purpose**: Retrieve credentials for a website plugin.
**Method**: `POST`
**Endpoint**: `/plugins/lookup`
**Authentication**: None
**Description**: Public endpoint used by the JS widget to find its associated collection.
**Payload**:
```json
{
  "website_url": "https://help.acme.com/login"
}
```
**Response**:
```json
{
  "is_active": true,
  "collection_id": "uuid",
  "plugin_token": "plg_..."
}
```

---

## Prompts API

### 1. Create System Prompt
**Purpose**: Define behavior for the AI assistant.
**Method**: `POST`
**Endpoint**: `/prompts/`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Sets the system instructions and parameters for a collection.
**Payload**:
```json
{
  "name": "Customer Support",
  "system_prompt": "You are a support agent...",
  "collection_id": "uuid",
  "model_name": "claude-3-haiku-20240307",
  "temperature": 0.5
}
```
**Response**: Created prompt object.

### 2. Test Prompt
**Purpose**: Preview how a prompt will be formatted.
**Method**: `POST`
**Endpoint**: `/prompts/{prompt_id}/test`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Returns the fully expanded prompt string.
**Payload**:
```json
{
  "test_query": "Hello",
  "test_context": "The user is John."
}
```
**Response**:
```json
{
  "formatted_prompt": "System: You are a support agent... Context: The user is John. User: Hello"
}
```

---

## Vector Databases API

### 1. Get Database Stats
**Purpose**: Monitor storage and document metrics.
**Method**: `GET`
**Endpoint**: `/vector_databases/{vector_db_id}/stats`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Returns granular metrics from the vector engine.
**Payload**: None
**Response**:
```json
{
  "document_count": 1500,
  "vector_count": 4500,
  "indexing_status": "ready"
}
```

---

## Websites & Analytics API

### 1. List Websites
**Purpose**: Retrieve all websites (tenants) in the system.
**Method**: `GET`
**Endpoint**: `/websites/`
**Authentication**: `Bearer <token>` (Required)
**Description**: Lists websites based on permissions.
**Payload**: None
**Response**:
```json
[
  {
    "website_id": "uuid",
    "name": "Acme Corp",
    "domain": "acme.com",
    "is_active": true
  }
]
```

### 2. Get Website Analytics
**Purpose**: Retrieve usage statistics for a website.
**Method**: `GET`
**Endpoint**: `/websites/{website_id}/analytics`
**Authentication**: `Bearer <token>` (Admin Required)
**Description**: Returns query counts and token usage.
**Payload**: None
**Response**:
```json
{
  "website_name": "Acme Corp",
  "query_analytics": {
    "total_queries": 150,
    "unique_users": 12,
    "total_tokens_used": 45000
  }
}
```

---

## Frontend API Usage

The frontend interacts with the backend strictly through authenticated requests. Most interactions are abstracted through the [api.ts](file:///c:/Users/nivin/Documents/Chatbot_RAG_System_UI_1/chatbot_frontend/src/utils/api.ts) utility.

### 1. Standard API Request (Logic Flow)
**API Name**: `apiRequest` (Internal Utility)
**Purpose**: Centralized wrapper for all fetch-based interactions.
**Authentication**: `Bearer <token>` (Automatically injected)
**Description**:
1. Fetches the current `user` from `AuthContext`.
2. Appends `Authorization: Bearer ${user.access_token}` to headers.
3. Performs the requested method (GET, POST, etc.) on the backend URL.
4. Handles common error status codes.

### 2. Streaming Chat Implementation
**API Name**: Assistant Response Streaming
**Purpose**: Provide real-time feedback during long AI generations.
**Method**: `POST`
**Endpoint**: `/chat/ask` (with `stream: true`)
**Description**: Instead of a standard JSON response, the backend emits Server-Sent Events (SSE). The frontend uses a reader on the response body to incrementally update the UI.

### 3. File Upload (Multipart)
**API Name**: `apiUpload`
**Purpose**: Securely transmit binary files.
**Method**: `POST`
**Endpoint**: `/files/upload`
**Description**: Uses a `FormData` object to encapsulate files and the `collection_id`. The utility manages the boundary headers automatically.

---

> [!NOTE]
> For a detailed walkthrough of frontend API logic and common pitfalls (like mixed `fetch` vs `api.ts` usage), see [walkthrough.md](file:///C:/Users/nivin/.gemini/antigravity/brain/701f3cca-6625-423b-9a7b-9036613afd3f/walkthrough.md).
