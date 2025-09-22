# 🚀 Production Deployment Guide

## 📋 **Setup Instructions**

### 1. **Backend Setup**

```bash
cd chatbot_backend

# Install dependencies
pip install -r requirements.txt

# Create .env file with all required variables
cp .env.example .env
# Edit .env with your actual values
```

### 2. **Environment Variables (.env)**

```env
# Claude AI Configuration
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_MODEL=claude-3-haiku-20240307
CLAUDE_MAX_TOKENS=1000
CLAUDE_TEMPERATURE=0.0

# Database Configuration
DATABASE_URL=sqlite:///./chatbot.db
# For PostgreSQL: postgresql://user:password@localhost/chatbot_db
# For MySQL: mysql://user:password@localhost/chatbot_db

# Vector Database
VECTOR_DB_URL=http://localhost:6333

# Authentication
SECRET_KEY=your-super-secret-jwt-key-here-make-it-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Upload Settings
MAX_FILE_SIZE_MB=25
ALLOWED_FILE_TYPES=pdf,docx,pptx,xlsx,txt

# Optional: Redis Cache
USE_REDIS=false
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 3. **Start Required Services**

```bash
# Start Qdrant Vector Database
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant

# Optional: Start Redis (if USE_REDIS=true)
docker run -p 6379:6379 redis:alpine
```

### 4. **Start Backend**

```bash
# Development
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. **Frontend Setup**

```bash
cd chatbot_frontend

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build
```

---

## 🧪 **Testing Guide**

### **1. Health Check Tests**

```bash
# Basic health check (public)
curl http://localhost:8000/system/health

# Detailed health check (requires auth)
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/system/health/detailed

# Individual service health checks (admin only)
curl -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     http://localhost:8000/system/health/qdrant

curl -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     http://localhost:8000/system/health/ai
```

### **2. File Storage Tests**

```bash
# Upload file (admin only)
curl -X POST \
     -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     -F "uploaded_file=@test_document.pdf" \
     http://localhost:8000/files/upload

# Download file
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/files/download/FILE_ID \
     --output downloaded_file.pdf

# Get file metadata
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/files/metadata/FILE_ID
```

### **3. Chat & Context Tests**

```bash
# Basic chat
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "What is the main topic?",
       "top_k": 5
     }' \
     http://localhost:8000/chat/ask

# Chat with context
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "Can you explain more about that?",
       "session_id": "test_session_123",
       "maintain_context": true,
       "conversation_history": [
         {
           "role": "user",
           "content": "What is the main topic?",
           "timestamp": "2025-01-19T10:00:00Z"
         },
         {
           "role": "assistant",
           "content": "The main topic is...",
           "timestamp": "2025-01-19T10:00:05Z"
         }
       ]
     }' \
     http://localhost:8000/chat/ask
```

### **4. Analytics Tests**

```bash
# Chat analytics (admin only)
curl -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     http://localhost:8000/chat/analytics

# Storage statistics (admin only)
curl -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     http://localhost:8000/system/stats/storage

# Complete system overview (admin only)
curl -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     http://localhost:8000/system/stats/overview
```

### **5. Activity Tracking Tests**

```bash
# Get recent activities
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/activity/recent

# Get activity statistics
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/activity/stats

# Get activities by type
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/activity/by-type/file_upload

# Get comprehensive activity summary
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/activity/summary

# Cleanup old activities (admin only)
curl -X DELETE \
     -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
     "http://localhost:8000/activity/cleanup?days_to_keep=30"
```

### **5. Session Management Tests**

```bash
# Get user sessions
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/chat/sessions

# Get session history
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/chat/sessions/SESSION_ID/history

# Delete session
curl -X DELETE \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/chat/sessions/SESSION_ID
```

---

## 📊 **Monitoring & Analytics**

### **System Health Dashboard**

Access the comprehensive health dashboard at:
- **Public Health**: `GET /system/health`
- **Detailed Health**: `GET /system/health/detailed`
- **System Overview**: `GET /system/stats/overview`

### **Key Metrics to Monitor**

1. **System Health**
   - Overall status (healthy/degraded/unhealthy)
   - Individual service health scores
   - Response times

2. **Storage Metrics**
   - Total files and storage size
   - File type distribution
   - Processing status

3. **Chat Analytics**
   - Total queries and sessions
   - Active users
   - Average queries per session
   - Processing times

4. **Performance Metrics**
   - Vector search response times
   - AI model response times
   - Database query performance

---

## 🔒 **Security Checklist**

### **Production Security**

- [ ] Change default JWT SECRET_KEY
- [ ] Use strong, unique passwords
- [ ] Enable HTTPS in production
- [ ] Restrict CORS origins to your domain
- [ ] Set up proper firewall rules
- [ ] Use environment variables for secrets
- [ ] Enable database connection encryption
- [ ] Set up proper backup procedures

### **File Security**

- [ ] Validate file types and sizes
- [ ] Scan uploaded files for malware
- [ ] Implement rate limiting
- [ ] Set up proper file permissions
- [ ] Monitor disk usage

### **API Security**

- [ ] Implement rate limiting
- [ ] Add request validation
- [ ] Log security events
- [ ] Monitor for suspicious activity
- [ ] Set up API key rotation

---

## 🚀 **Production Deployment**

### **Docker Deployment**

```dockerfile
# Dockerfile for backend
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### **Docker Compose**

```yaml
version: '3.8'
services:
  backend:
    build: ./chatbot_backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/chatbot
      - VECTOR_DB_URL=http://qdrant:6333
    depends_on:
      - db
      - qdrant

  frontend:
    build: ./chatbot_frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=chatbot
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
  qdrant_data:
```

### **Cloud Deployment Options**

1. **Railway/Heroku**
   - Easy deployment with git integration
   - Automatic scaling
   - Built-in monitoring

2. **AWS/GCP/Azure**
   - Container services (ECS, Cloud Run, Container Instances)
   - Managed databases
   - CDN for frontend

3. **DigitalOcean/Linode**
   - VPS with Docker
   - Managed databases
   - Load balancers

---

## 📈 **Performance Optimization**

### **Database Optimization**

- Use connection pooling
- Add database indexes
- Implement query optimization
- Set up read replicas for analytics

### **Vector Database Optimization**

- Optimize vector dimensions
- Use appropriate distance metrics
- Implement proper indexing
- Monitor memory usage

### **Caching Strategy**

- Enable Redis for frequent queries
- Implement response caching
- Use CDN for static assets
- Cache vector search results

### **Scaling Considerations**

- Horizontal scaling with load balancers
- Database sharding for large datasets
- Microservices architecture
- Queue systems for background tasks

---

## 🔧 **Troubleshooting**

### **Common Issues**

1. **Database Connection Errors**
   - Check DATABASE_URL format
   - Verify database server is running
   - Check network connectivity

2. **Vector Database Issues**
   - Ensure Qdrant is running on correct port
   - Check VECTOR_DB_URL configuration
   - Verify collection creation

3. **Authentication Problems**
   - Verify JWT SECRET_KEY
   - Check token expiration
   - Validate user credentials

4. **File Upload Issues**
   - Check file size limits
   - Verify upload directory permissions
   - Validate file types

5. **File Download Issues**
   - Verify file exists in database
   - Check file path permissions
   - Ensure proper JWT authentication

6. **File Delete Issues**
   - Check admin role permissions
   - Verify vector database cleanup
   - Check cache invalidation

7. **Activity Tracking Issues**
   - Verify activity_logs directory permissions
   - Check JSON file write permissions
   - Ensure proper file cleanup schedules

### **Debug Endpoints**

- `/chat/debug/search` - Test vector search
- `/files/debug/vector-stats` - Check vector database
- `/system/health/detailed` - Comprehensive health check

Your production-ready RAG chatbot system is now complete with comprehensive monitoring, analytics, and deployment capabilities! 🎉
