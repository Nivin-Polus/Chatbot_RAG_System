# Multi-Tenant RAG Chatbot System Guide

## Overview

This guide covers the comprehensive multi-tenant architecture implemented for the RAG Chatbot System. The system now supports multiple departments/companies using the same infrastructure with complete data isolation and role-based access control.

## 🏗️ Architecture Overview

### Multi-Tenant Strategy

The system implements **logical partitioning** using:
- **One shared vector database** (Qdrant) with metadata filtering
- **MySQL database** for relational data with tenant isolation
- **Role-based access control** with three distinct user roles
- **Granular file permissions** for fine-grained access control

### Key Components

1. **Websites/Departments** - Tenant isolation units
2. **Users** - Multi-role user system (super_admin, user_admin, user)
3. **Files** - Department-scoped with granular access control
4. **Vector Store** - Shared collection with metadata filtering
5. **Query Logs** - Usage tracking and analytics per tenant

## 👥 User Roles & Permissions

### Super Admin
- **Global access** across all websites/departments
- Can create, modify, and delete websites
- Can create and manage all user types
- Access to global analytics and system monitoring
- **No website association** (website_id = null)

**Default Account:** `superadmin/superadmin123`

### User Admin
- **Department-scoped** administrative access
- Can manage users within their website only
- Can upload and manage files for their department
- Can grant file access to users in their department
- Access to department analytics
- **Tied to specific website** (website_id required)

**Default Account:** `admin/admin123` (Default Organization)

### User
- **Limited access** within their department
- Can only access explicitly granted files
- Can upload files (if permitted)
- Can chat with documents they have access to
- **Tied to specific website** (website_id required)

**Default Account:** `user/user123` (Default Organization)

## 🗄️ Database Schema

### Core Tables

#### websites
```sql
CREATE TABLE websites (
    website_id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    max_users INTEGER DEFAULT 100,
    max_files INTEGER DEFAULT 1000,
    max_storage_mb INTEGER DEFAULT 10240,
    logo_url VARCHAR(500),
    primary_color VARCHAR(7) DEFAULT '#6366f1',
    secondary_color VARCHAR(7) DEFAULT '#8b5cf6',
    admin_email VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### users (Updated)
```sql
CREATE TABLE users (
    user_id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    website_id VARCHAR(36) REFERENCES websites(website_id),
    role VARCHAR(20) DEFAULT 'user', -- super_admin, user_admin, user
    is_active BOOLEAN DEFAULT TRUE,
    phone VARCHAR(50),
    department VARCHAR(100),
    job_title VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login DATETIME,
    INDEX idx_username_website (username, website_id)
);
```

#### file_metadata (Updated)
```sql
CREATE TABLE file_metadata (
    file_id VARCHAR(36) PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    website_id VARCHAR(36) NOT NULL REFERENCES websites(website_id),
    uploader_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'pending',
    chunk_count INTEGER DEFAULT 0,
    description TEXT,
    tags VARCHAR(500),
    is_public BOOLEAN DEFAULT FALSE,
    mime_type VARCHAR(100),
    vector_collection VARCHAR(100),
    vector_indexed BOOLEAN DEFAULT FALSE,
    INDEX idx_website_id (website_id)
);
```

#### user_file_access
```sql
CREATE TABLE user_file_access (
    access_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    file_id VARCHAR(36) NOT NULL REFERENCES file_metadata(file_id),
    can_read BOOLEAN DEFAULT TRUE,
    can_download BOOLEAN DEFAULT FALSE,
    can_delete BOOLEAN DEFAULT FALSE,
    granted_by VARCHAR(36) NOT NULL REFERENCES users(user_id),
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    notes TEXT,
    INDEX idx_user_file (user_id, file_id)
);
```

#### query_logs
```sql
CREATE TABLE query_logs (
    query_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(user_id),
    website_id VARCHAR(36) NOT NULL REFERENCES websites(website_id),
    session_id VARCHAR(36),
    user_query TEXT NOT NULL,
    ai_response TEXT,
    query_type VARCHAR(50) DEFAULT 'chat',
    processing_time_ms INTEGER,
    tokens_used INTEGER,
    chunks_retrieved INTEGER,
    context_used TEXT,
    files_accessed TEXT,
    vector_search_score FLOAT,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_website_user (website_id, user_id),
    INDEX idx_created_at (created_at)
);
```

## 🔍 Vector Database Strategy

### Single Collection with Metadata Filtering

The system uses **one shared Qdrant collection** (`multitenant_documents`) with metadata-based filtering:

```python
# Document metadata structure
{
    "website_id": "uuid-of-department",
    "file_id": "uuid-of-file",
    "file_name": "document.pdf",
    "file_type": "pdf",
    "uploader_id": "uuid-of-uploader",
    "tags": ["finance", "policy"],
    "is_public": false,
    "text": "document content...",
    "chunk_index": 0
}
```

### Search with Tenant Isolation

```python
# Search filters ensure tenant isolation
search_filter = Filter(
    must=[
        # Tenant isolation
        FieldCondition(key="website_id", match=MatchValue(value=user_website_id)),
        # File access control
        FieldCondition(key="file_id", match=MatchValue(value=accessible_file_ids))
    ]
)
```

### Benefits

1. **Single Infrastructure** - One Qdrant instance for all tenants
2. **Strict Isolation** - Metadata filters prevent cross-tenant data access
3. **Scalable** - Efficient indexing and querying
4. **Fine-grained Control** - File-level access permissions

## 🔐 Access Control Matrix

| Role | Create Websites | Manage Users | Upload Files | Access Files | View Analytics | Delete Data |
|------|----------------|--------------|--------------|--------------|----------------|-------------|
| **Super Admin** | ✅ All | ✅ All | ✅ All | ✅ All | ✅ Global | ✅ All |
| **User Admin** | ❌ | ✅ Own Website | ✅ Own Website | ✅ Own Website | ✅ Own Website | ✅ Own Files |
| **User** | ❌ | ❌ | ✅ If Permitted | ✅ Granted Only | ❌ | ✅ Own Files |

## 📡 API Endpoints

### Website Management

```bash
# List websites (filtered by permissions)
GET /websites/

# Get website details with stats
GET /websites/{website_id}

# Create website (super admin only)
POST /websites/

# Update website
PUT /websites/{website_id}

# Delete website (super admin only)
DELETE /websites/{website_id}

# Get website analytics
GET /websites/{website_id}/analytics
```

### User Management

```bash
# Get current user info with permissions
GET /users/me

# List users (filtered by permissions)
GET /users/

# Get user details
GET /users/{user_id}

# Create user
POST /users/

# Update user
PUT /users/{user_id}

# Deactivate user
DELETE /users/{user_id}

# Activate user
POST /users/{user_id}/activate

# Get user's accessible files
GET /users/{user_id}/accessible-files
```

### File Access Management

```bash
# Grant file access to user
POST /files/{file_id}/access

# Update file access permissions
PUT /files/{file_id}/access/{access_id}

# Revoke file access
DELETE /files/{file_id}/access/{access_id}

# List file access permissions
GET /files/{file_id}/access
```

## 🚀 Setup Instructions

### 1. Database Setup

The multi-tenant system builds on the existing MySQL setup:

```bash
# Use existing MySQL setup
python setup_mysql.py
```

### 2. Environment Configuration

Update your `.env` file (already configured for MySQL):

```env
# Database Configuration (already set)
DATABASE_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=chatbot_rag
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password

# Multi-tenant specific settings
DEFAULT_WEBSITE_NAME="Your Organization"
DEFAULT_WEBSITE_DOMAIN="yourdomain.com"
```

### 3. Application Startup

```bash
# Start the application (will auto-create multi-tenant schema)
python -m uvicorn app.main:app --reload
```

### 4. Initial Setup

The system automatically creates:
- Default website: "Default Organization"
- Super admin: `superadmin/superadmin123`
- User admin: `admin/admin123` (Default Organization)
- Regular user: `user/user123` (Default Organization)

## 🔧 Usage Workflows

### Creating a New Department

1. **Super Admin** creates a new website:
```bash
POST /websites/
{
    "name": "Finance Department",
    "domain": "finance.company.com",
    "description": "Finance department chatbot",
    "admin_email": "finance-admin@company.com"
}
```

2. **Super Admin** creates a user admin for the department:
```bash
POST /users/
{
    "username": "finance_admin",
    "password": "secure_password",
    "email": "finance-admin@company.com",
    "full_name": "Finance Administrator",
    "website_id": "finance-website-id",
    "role": "user_admin"
}
```

### Adding Users to Department

**User Admin** creates users in their department:
```bash
POST /users/
{
    "username": "john_doe",
    "password": "user_password",
    "email": "john@company.com",
    "full_name": "John Doe",
    "website_id": "finance-website-id",
    "role": "user",
    "department": "Accounting"
}
```

### File Upload and Access Control

1. **User Admin** uploads a file:
```bash
POST /files/upload
# File gets associated with user's website_id
```

2. **User Admin** grants access to specific users:
```bash
POST /files/{file_id}/access
{
    "user_id": "john-doe-id",
    "can_read": true,
    "can_download": true,
    "expires_at": "2024-12-31T23:59:59Z"
}
```

### Querying with Access Control

When a user queries the system:
1. System identifies user's website and accessible files
2. Vector search is filtered by website_id and accessible file_ids
3. Only relevant, permitted documents are returned
4. Query is logged for analytics

## 📊 Analytics and Monitoring

### Website-Level Analytics

```bash
GET /websites/{website_id}/analytics?days=30
```

Returns:
- Query statistics (total, unique users, avg processing time)
- Usage statistics (users, files, storage)
- Vector database statistics
- Performance metrics

### User Activity Tracking

All queries are logged with:
- User and website context
- Performance metrics
- Files accessed
- Error tracking

### System Health Monitoring

```bash
GET /system/health
```

Includes multi-tenant specific health checks:
- Database connectivity per tenant
- Vector store statistics
- Quota usage monitoring

## 🔒 Security Considerations

### Data Isolation

1. **Database Level**: All queries include website_id filters
2. **Vector Store Level**: Metadata filtering prevents cross-tenant access
3. **API Level**: Permission checks on every endpoint
4. **File System Level**: Organized by website_id

### Authentication & Authorization

1. **JWT Tokens** include user role and website_id
2. **Role-based middleware** enforces permissions
3. **Granular file access** with expiration support
4. **Audit logging** for all administrative actions

### Quota Management

1. **User limits** per website
2. **File count limits** per website
3. **Storage limits** per website
4. **Automatic quota checking** on resource creation

## 🚨 Migration from Single-Tenant

If you have existing data in the single-tenant system:

### 1. Backup Existing Data
```bash
# Backup your existing MySQL database
mysqldump -u user -p chatbot_rag > backup_before_multitenant.sql
```

### 2. Run Migration
The system will automatically:
- Create new multi-tenant tables
- Migrate existing users to default website
- Update file metadata with website associations
- Preserve all existing functionality

### 3. Verify Migration
```bash
# Check system health
curl http://localhost:8000/system/health

# Verify user access
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/users/me
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Permission Denied Errors
```
HTTP 403: Access denied to this website
```
**Solution**: Verify user's website_id matches the resource's website_id

#### 2. No Search Results
```
User has no accessible files in website
```
**Solution**: Grant file access using `/files/{file_id}/access` endpoint

#### 3. Quota Exceeded
```
Website user quota exceeded
```
**Solution**: Increase website limits or remove inactive users

### Debug Endpoints

```bash
# Get user's accessible files
GET /users/{user_id}/accessible-files

# Get website statistics
GET /websites/{website_id}

# Check vector store stats
GET /system/health
```

## 📈 Performance Optimization

### Database Indexes

The system creates optimized indexes for:
- `users(username, website_id)` - Fast user lookups
- `file_metadata(website_id)` - Tenant filtering
- `user_file_access(user_id, file_id)` - Permission checks
- `query_logs(website_id, user_id, created_at)` - Analytics queries

### Vector Store Optimization

- **Metadata indexes** on website_id, file_id, uploader_id
- **Efficient filtering** using Qdrant's native capabilities
- **Connection pooling** for high-concurrency scenarios

### Caching Strategy

Consider implementing:
- **User permission caching** (Redis)
- **File access lists caching**
- **Website configuration caching**

## 🎯 Best Practices

### For Super Admins

1. **Create dedicated websites** for each department
2. **Assign user admins** to manage their departments
3. **Monitor quota usage** regularly
4. **Review analytics** for system optimization

### For User Admins

1. **Grant minimal necessary permissions** to users
2. **Use file expiration** for temporary access
3. **Organize files with tags** for better discoverability
4. **Monitor department usage** through analytics

### For Developers

1. **Always check permissions** in custom endpoints
2. **Use the permission helper classes** for consistency
3. **Log important actions** for audit trails
4. **Test with different user roles** during development

## 🆘 Support

For issues or questions:

1. Check the **troubleshooting section** above
2. Review **application logs** for detailed error messages
3. Use **debug endpoints** to verify system state
4. Consult the **API documentation** at `/docs`

The multi-tenant system provides enterprise-grade isolation and security while maintaining the simplicity and performance of the original RAG chatbot system.
