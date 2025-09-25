# MySQL Database Migration Guide

## Overview

This guide covers the complete migration from local storage (SQLite + JSON files) to MySQL database for the RAG Chatbot System. All user data, file metadata, chat sessions, and logs are now stored in a configurable MySQL database.

## 🚀 Quick Start

### 1. Install MySQL Server

**Windows:**
```bash
# Download and install MySQL from https://dev.mysql.com/downloads/mysql/
# Or use chocolatey
choco install mysql

# Start MySQL service
net start mysql80
```

**Linux/Ubuntu:**
```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
```

**macOS:**
```bash
brew install mysql
brew services start mysql
```

### 2. Create Database and User

```sql
-- Connect to MySQL as root
mysql -u root -p

-- Create database
CREATE DATABASE chatbot_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (optional, you can use root)
CREATE USER 'chatbot_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON chatbot_rag.* TO 'chatbot_user'@'localhost';
FLUSH PRIVILEGES;

-- Exit MySQL
EXIT;
```

### 3. Configure Environment

Copy and update your `.env` file:

```bash
cp .env.example .env
```

Update the database configuration in `.env`:

```env
# Database Configuration - MySQL
DATABASE_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=chatbot_rag
DATABASE_USER=chatbot_user
DATABASE_PASSWORD=your_secure_password
DATABASE_CHARSET=utf8mb4
DATABASE_COLLATION=utf8mb4_unicode_ci

# Connection Pool Settings
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# SSL Configuration (if needed)
DATABASE_SSL_DISABLED=true
```

### 4. Install Dependencies

```bash
pip install PyMySQL==1.1.1 cryptography==43.0.3
```

### 5. Run Setup Script

```bash
cd chatbot_backend
python setup_mysql.py
```

### 6. Start Application

```bash
python -m uvicorn app.main:app --reload
```

## 📋 Configuration Options

### Database Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASE_TYPE` | `mysql` | Database type (mysql, sqlite, postgresql) |
| `DATABASE_HOST` | `localhost` | MySQL server hostname |
| `DATABASE_PORT` | `3306` | MySQL server port |
| `DATABASE_NAME` | `chatbot_rag` | Database name |
| `DATABASE_USER` | `root` | MySQL username |
| `DATABASE_PASSWORD` | `` | MySQL password |
| `DATABASE_CHARSET` | `utf8mb4` | Character set |
| `DATABASE_COLLATION` | `utf8mb4_unicode_ci` | Collation |

### Connection Pool Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASE_POOL_SIZE` | `10` | Base connection pool size |
| `DATABASE_MAX_OVERFLOW` | `20` | Maximum overflow connections |
| `DATABASE_POOL_TIMEOUT` | `30` | Connection timeout (seconds) |
| `DATABASE_POOL_RECYCLE` | `3600` | Connection recycle time (seconds) |

### SSL Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASE_SSL_DISABLED` | `false` | Disable SSL connections |
| `DATABASE_SSL_CA` | `` | SSL CA certificate path |
| `DATABASE_SSL_CERT` | `` | SSL client certificate path |
| `DATABASE_SSL_KEY` | `` | SSL client key path |

## 🗄️ Database Schema

### Tables Created

1. **users** - User accounts and authentication
2. **file_metadata** - Uploaded file information
3. **chat_sessions** - Chat session tracking
4. **chat_queries** - Individual chat queries and responses

### User Table Structure

```sql
CREATE TABLE users (
    user_id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login DATETIME,
    INDEX idx_username (username),
    INDEX idx_email (email)
);
```

### File Metadata Table Structure

```sql
CREATE TABLE file_metadata (
    file_id VARCHAR(36) PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    uploader_id VARCHAR(36) NOT NULL,
    upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'pending',
    chunk_count INTEGER DEFAULT 0
);
```

## 🔧 Advanced Configuration

### Production Settings

For production environments, consider these additional settings:

```env
# Production Database Configuration
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=50
DATABASE_POOL_TIMEOUT=60
DATABASE_POOL_RECYCLE=1800

# Enable SSL for production
DATABASE_SSL_DISABLED=false
DATABASE_SSL_CA=/path/to/ca-cert.pem
DATABASE_SSL_CERT=/path/to/client-cert.pem
DATABASE_SSL_KEY=/path/to/client-key.pem
```

### Multiple Environment Support

You can use different databases for different environments:

**Development (.env.dev):**
```env
DATABASE_NAME=chatbot_rag_dev
DATABASE_USER=dev_user
```

**Testing (.env.test):**
```env
DATABASE_NAME=chatbot_rag_test
DATABASE_USER=test_user
```

**Production (.env.prod):**
```env
DATABASE_NAME=chatbot_rag_prod
DATABASE_USER=prod_user
DATABASE_SSL_DISABLED=false
```

## 🔍 Monitoring and Health Checks

### Database Health Endpoint

```bash
curl http://localhost:8000/system/health
```

Response:
```json
{
  "database": {
    "status": "healthy",
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "database": "chatbot_rag",
    "version": "8.0.35",
    "pool_size": 10
  }
}
```

### Database Statistics

```bash
curl http://localhost:8000/system/database/stats
```

Response:
```json
{
  "tables": [
    {
      "name": "users",
      "rows": 2,
      "data_size": 16384,
      "index_size": 16384
    }
  ],
  "total_rows": 10,
  "total_size_bytes": 65536,
  "total_size_mb": 0.06
}
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Connection Refused
```
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```

**Solutions:**
- Check if MySQL server is running: `systemctl status mysql`
- Verify host and port in configuration
- Check firewall settings

#### 2. Access Denied
```
pymysql.err.OperationalError: (1045, "Access denied for user")
```

**Solutions:**
- Verify username and password
- Check user permissions: `SHOW GRANTS FOR 'username'@'localhost';`
- Reset password if needed

#### 3. Database Doesn't Exist
```
pymysql.err.OperationalError: (1049, "Unknown database 'chatbot_rag'")
```

**Solutions:**
- Run the setup script: `python setup_mysql.py`
- Create database manually: `CREATE DATABASE chatbot_rag;`

#### 4. SSL Connection Issues
```
pymysql.err.OperationalError: SSL connection error
```

**Solutions:**
- Set `DATABASE_SSL_DISABLED=true` for local development
- Configure proper SSL certificates for production

### Debug Mode

Enable SQL query logging by setting in `database.py`:
```python
engine = create_engine(
    database_url,
    echo=True  # Enable SQL logging
)
```

## 📊 Performance Optimization

### MySQL Configuration

Add to `/etc/mysql/mysql.conf.d/mysqld.cnf`:

```ini
[mysqld]
# Connection settings
max_connections = 200
connect_timeout = 60
wait_timeout = 28800

# Buffer settings
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2

# Character set
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

### Application-Level Optimization

1. **Connection Pooling**: Already configured with SQLAlchemy
2. **Query Optimization**: Use indexes on frequently queried columns
3. **Batch Operations**: Use bulk inserts for large datasets

## 🔄 Migration from SQLite

If you have existing SQLite data, you can migrate it:

### 1. Export SQLite Data

```python
import sqlite3
import json

# Connect to SQLite
conn = sqlite3.connect('chatbot.db')
cursor = conn.cursor()

# Export users (if any)
cursor.execute("SELECT * FROM users")
users = cursor.fetchall()

# Export file metadata
cursor.execute("SELECT * FROM file_metadata")
files = cursor.fetchall()

# Save to JSON for manual import
with open('migration_data.json', 'w') as f:
    json.dump({
        'users': users,
        'files': files
    }, f, indent=2)
```

### 2. Import to MySQL

Use the setup script or manually insert the data into MySQL.

## 🔐 Security Considerations

### 1. Database Security

- Use strong passwords
- Create dedicated database users with minimal privileges
- Enable SSL for production
- Regular security updates

### 2. Application Security

- Password hashing with bcrypt
- JWT token expiration
- Input validation and sanitization
- SQL injection prevention (SQLAlchemy ORM)

### 3. Network Security

- Firewall configuration
- VPN for remote database access
- Regular security audits

## 📝 Default Accounts

The system creates these default accounts:

| Username | Password | Role | Email |
|----------|----------|------|-------|
| `admin` | `admin123` | admin | admin@chatbot.local |
| `user` | `user123` | user | user@chatbot.local |

**⚠️ Important:** Change these default passwords in production!

## 🆘 Support

If you encounter issues:

1. Check the application logs
2. Verify MySQL server status
3. Test database connection manually
4. Review configuration settings
5. Check firewall and network settings

For additional help, refer to:
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)
