# Python 3.10 Setup Guide for RAG Chatbot System

## Overview
This guide will help you set up a clean Python 3.10 environment for the RAG Chatbot System, especially if you've made changes to your virtual environment for another project.

## Prerequisites
- Python 3.10.x installed on your system
- Git (for cloning/managing the repository)

## Step 1: Create a Fresh Virtual Environment

### Option A: Using venv (Recommended)
```bash
# Navigate to your project directory
cd "C:\Users\nivin\Documents\Chatbot_RAG_System_UI_1\chatbot_backend"

# Create a new virtual environment
python -m venv venv_chatbot

# Activate the virtual environment
# On Windows:
venv_chatbot\Scripts\activate
# On macOS/Linux:
# source venv_chatbot/bin/activate
```

### Option B: Using conda (Alternative)
```bash
# Create a new conda environment with Python 3.10
conda create -n chatbot_rag python=3.10

# Activate the environment
conda activate chatbot_rag
```

## Step 2: Verify Python Version
```bash
python --version
# Should output: Python 3.10.x
```

## Step 3: Upgrade pip and Install Dependencies
```bash
# Upgrade pip to latest version
python -m pip install --upgrade pip

# Install wheel and setuptools first
pip install wheel setuptools

# Install all dependencies from requirements.txt
pip install -r requirements.txt
```

## Step 4: Verify Installation
Run the dependency check script:
```bash
python start_server.py --check-deps
```

Or manually verify key packages:
```bash
python -c "
import fastapi
import sqlalchemy
import anthropic
import qdrant_client
import sentence_transformers
print('✅ All core packages installed successfully!')
"
```

## Step 5: Environment Configuration
1. Copy the example environment file:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` file with your configuration:
   ```env
   # Claude AI API Key (Required)
   CLAUDE_API_KEY=your_claude_api_key_here
   
   # Database Configuration
   DATABASE_TYPE=mysql
   DATABASE_HOST=localhost
   DATABASE_PORT=3306
   DATABASE_NAME=chatbot_rag
   DATABASE_USER=root
   DATABASE_PASSWORD=your_mysql_password
   
   # Server Configuration
   SERVER_HOST=0.0.0.0
   SERVER_PORT=8000
   
   # JWT Secret (Generate a secure secret)
   SECRET_KEY=your_jwt_secret_key_here
   ```

## Step 6: Database Setup
```bash
# Initialize the database schema
python setup_mysql.py

# Or run the initialization script
python initialize_schema.py
```

## Step 7: Start the Application
```bash
# Start the FastAPI server
python start_server.py

# Or use uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Troubleshooting Common Issues

### Issue 1: PyTorch Installation Problems
If you encounter issues with PyTorch installation:
```bash
# Install PyTorch with CPU support only (smaller download)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Issue 2: Qdrant Client Issues
If Qdrant client fails to install:
```bash
# Install with specific version
pip install qdrant-client==1.7.3
```

### Issue 3: Windows-specific Issues
If you encounter issues on Windows:
```bash
# Install Microsoft Visual C++ Build Tools if needed
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Install pywin32 manually if needed
pip install pywin32==306
```

### Issue 4: Dependency Conflicts
If you encounter dependency conflicts:
```bash
# Create a completely fresh environment
deactivate  # Exit current environment
rm -rf venv_chatbot  # Remove old environment
python -m venv venv_chatbot_fresh  # Create new one
venv_chatbot_fresh\Scripts\activate  # Activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue 5: SSL/Certificate Issues
If you encounter SSL certificate issues:
```bash
# Upgrade certificates
pip install --upgrade certifi

# Or install with trusted hosts
pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

## Package Versions Explanation

The updated `requirements.txt` uses version ranges instead of exact pins for better compatibility:

- **Core Framework**: FastAPI, Uvicorn, Starlette with compatible versions
- **Database**: SQLAlchemy 2.x with MySQL support via PyMySQL
- **AI/ML**: Anthropic Claude API, Sentence Transformers, PyTorch (CPU version)
- **Vector DB**: Qdrant client for vector storage
- **File Processing**: Support for PDF, DOCX, PPTX, XLSX files
- **Security**: Passlib with bcrypt, JWT tokens, cryptography

## Performance Optimization

### For Development:
```bash
# Install with no cache to ensure fresh packages
pip install --no-cache-dir -r requirements.txt
```

### For Production:
```bash
# Install with specific torch version for better performance
pip install torch==2.1.0+cpu torchvision==0.16.0+cpu --index-url https://download.pytorch.org/whl/cpu
```

## Testing the Installation

1. **Test Database Connection**:
   ```bash
   python test_db.py
   ```

2. **Test Vector Store**:
   ```bash
   python -c "
   from app.services.multitenant_vector_store import MultiTenantVectorStore
   store = MultiTenantVectorStore()
   print('✅ Vector store initialized successfully!')
   "
   ```

3. **Test API Endpoints**:
   ```bash
   # Start server in one terminal
   python start_server.py
   
   # Test in another terminal
   curl http://localhost:8000/health
   ```

## Next Steps

After successful installation:

1. **Configure Claude API**: Add your Claude API key to `.env`
2. **Set up MySQL**: Ensure MySQL server is running and accessible
3. **Initialize Data**: Run the setup scripts to create default users
4. **Start Frontend**: Navigate to the frontend directory and start React app
5. **Test Upload**: Try uploading a document and asking questions

## Support

If you continue to face issues:

1. Check Python version: `python --version`
2. Check pip version: `pip --version`
3. List installed packages: `pip list`
4. Check for conflicts: `pip check`

The requirements.txt has been optimized for Python 3.10 compatibility with proper version ranges to avoid conflicts while ensuring all features work correctly.
