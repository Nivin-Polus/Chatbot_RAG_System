# Database Setup Guide - Multi-Tenant RAG Chatbot

## 🚨 Quick Fix for Your Current Issue

### Problem
You're getting: `Connection() got an unexpected keyword argument 'charset'`

### Solution
The issue was in the database configuration where `charset` was being passed as a connection argument instead of being in the URL. This has been fixed.

## 🔧 Step-by-Step Setup

### 1. Update Your .env File

Make sure your `.env` file has the correct database name:

```env
# Database Configuration - MySQL
DATABASE_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=Chatbot_1
DATABASE_USER=root
DATABASE_PASSWORD=your_actual_mysql_password
DATABASE_CHARSET=utf8mb4
DATABASE_COLLATION=utf8mb4_unicode_ci
```

### 2. Test Database Connection

Run the database test script:

```bash
cd chatbot_backend
python test_db_connection.py
```

This will:
- ✅ Test your MySQL server connection
- ✅ Check if the `Chatbot_1` database exists
- ✅ Create the database if it doesn't exist
- ✅ Verify you can connect to the specific database

### 3. Start the Server

After the database test passes:

```bash
python start_server.py
```

## 🗄️ Database Schema Information

### About MySQL Schemas
- In MySQL, **database name = schema name**
- Your `DATABASE_NAME=Chatbot_1` is both the database and schema
- No separate schema parameter needed

### What Gets Created
The multi-tenant system will create these tables:

1. **`websites`** - Department/tenant definitions
2. **`users`** - Multi-role user system  
3. **`file_metadata`** - Files with department isolation
4. **`user_file_access`** - Granular file permissions
5. **`query_logs`** - Usage tracking per tenant

## 🚨 Common Issues & Solutions

### Issue 1: Database Doesn't Exist
```
ERROR: Unknown database 'Chatbot_1'
```
**Solution**: Run `test_db_connection.py` and let it create the database

### Issue 2: Permission Denied
```
ERROR: Access denied for user 'root'@'localhost'
```
**Solution**: Check your MySQL password in `.env` file

### Issue 3: MySQL Server Not Running
```
ERROR: Can't connect to MySQL server
```
**Solution**: Start your MySQL server

### Issue 4: Charset Issues
```
ERROR: Connection() got an unexpected keyword argument 'charset'
```
**Solution**: This has been fixed in the latest config. Update your code.

## 🔍 Verification Steps

After setup, verify everything works:

1. **Check Database Connection**:
   ```bash
   python test_db_connection.py
   ```

2. **Start Server**:
   ```bash
   python start_server.py
   ```

3. **Check API Documentation**:
   Open: http://localhost:8000/docs

4. **Test Default Accounts**:
   - Super Admin: `superadmin/superadmin123`
   - User Admin: `admin/admin123`  
   - Regular User: `user/user123`

## 📊 Database Structure

```sql
-- Example of what gets created
CREATE DATABASE Chatbot_1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE Chatbot_1;

-- Tables will be created automatically by SQLAlchemy
-- websites, users, file_metadata, user_file_access, query_logs
```

## 🆘 Still Having Issues?

1. **Check MySQL Service**: Ensure MySQL is running
2. **Verify Credentials**: Test login with MySQL client
3. **Check Permissions**: Ensure user can create databases
4. **Review Logs**: Check the detailed error messages
5. **Run Test Script**: Use `test_db_connection.py` for diagnostics

## 🎯 Next Steps

Once database is working:

1. **Create Departments**: Use Super Admin to create websites
2. **Add Users**: Assign User Admins to departments
3. **Upload Files**: Test file upload with department isolation
4. **Test Chat**: Verify multi-tenant chat functionality

Your database name `Chatbot_1` is perfectly fine - it will serve as both the database and schema name in MySQL!
