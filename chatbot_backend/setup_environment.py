#!/usr/bin/env python3
"""
Environment Setup Script for RAG Chatbot System
Automates the setup process for Python 3.10 environment
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def run_command(command, check=True, capture_output=False):
    """Run a shell command and handle errors"""
    try:
        if capture_output:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=check)
            return result.stdout.strip()
        else:
            subprocess.run(command, shell=True, check=check)
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {command}")
        print(f"Error: {e}")
        return False

def check_python_version():
    """Check if Python 3.10 is being used"""
    version = sys.version_info
    print(f"🐍 Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor != 10:
        print("⚠️  Warning: This project is optimized for Python 3.10")
        print("   You may encounter compatibility issues with other versions")
        return False
    
    print("✅ Python 3.10 detected - perfect!")
    return True

def check_pip():
    """Check and upgrade pip"""
    print("\n📦 Checking pip...")
    
    # Check pip version
    pip_version = run_command("pip --version", capture_output=True)
    if pip_version:
        print(f"📦 Current pip: {pip_version}")
    
    # Upgrade pip
    print("📦 Upgrading pip...")
    if run_command("python -m pip install --upgrade pip"):
        print("✅ pip upgraded successfully")
        return True
    else:
        print("❌ Failed to upgrade pip")
        return False

def install_dependencies():
    """Install dependencies from requirements.txt"""
    print("\n📚 Installing dependencies...")
    
    # Check if requirements.txt exists
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found!")
        return False
    
    # Install wheel and setuptools first
    print("📚 Installing build tools...")
    if not run_command("pip install wheel setuptools"):
        print("❌ Failed to install build tools")
        return False
    
    # Install main dependencies
    print("📚 Installing main dependencies (this may take a few minutes)...")
    if run_command("pip install -r requirements.txt"):
        print("✅ Dependencies installed successfully")
        return True
    else:
        print("❌ Failed to install dependencies")
        print("💡 Try running: pip install --no-cache-dir -r requirements.txt")
        return False

def verify_installation():
    """Verify that key packages are installed correctly"""
    print("\n🔍 Verifying installation...")
    
    packages_to_check = [
        ("fastapi", "FastAPI web framework"),
        ("sqlalchemy", "Database ORM"),
        ("anthropic", "Claude AI client"),
        ("qdrant_client", "Vector database client"),
        ("sentence_transformers", "Embedding models"),
        ("torch", "PyTorch ML framework"),
        ("pandas", "Data processing"),
        ("pypdf", "PDF processing")
    ]
    
    failed_packages = []
    
    for package, description in packages_to_check:
        try:
            __import__(package)
            print(f"✅ {package} - {description}")
        except ImportError:
            print(f"❌ {package} - {description}")
            failed_packages.append(package)
    
    if failed_packages:
        print(f"\n⚠️  Failed to import: {', '.join(failed_packages)}")
        print("💡 Try reinstalling these packages individually:")
        for package in failed_packages:
            print(f"   pip install {package}")
        return False
    
    print("\n✅ All key packages verified successfully!")
    return True

def check_environment_file():
    """Check and create .env file if needed"""
    print("\n⚙️  Checking environment configuration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✅ .env file exists")
        return True
    
    if env_example.exists():
        print("📋 Creating .env from .env.example...")
        try:
            import shutil
            shutil.copy(env_example, env_file)
            print("✅ .env file created from template")
            print("⚠️  Please edit .env file with your configuration:")
            print("   - Add your Claude API key")
            print("   - Configure database settings")
            print("   - Set JWT secret key")
            return True
        except Exception as e:
            print(f"❌ Failed to copy .env.example: {e}")
    
    print("⚠️  No .env file found. Please create one with your configuration.")
    return False

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    
    directories = [
        "uploads",
        "activity_logs",
        "logs"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory exists: {directory}")

def main():
    """Main setup function"""
    print("🚀 RAG Chatbot System - Environment Setup")
    print("=" * 50)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📂 Working directory: {script_dir}")
    
    # Check Python version
    if not check_python_version():
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            sys.exit(1)
    
    # Check and upgrade pip
    if not check_pip():
        print("❌ Failed to setup pip")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Verify installation
    if not verify_installation():
        print("❌ Installation verification failed")
        sys.exit(1)
    
    # Check environment file
    check_environment_file()
    
    # Create directories
    create_directories()
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your configuration")
    print("2. Set up your MySQL database")
    print("3. Add your Claude API key to .env")
    print("4. Run: python setup_mysql.py")
    print("5. Start the server: python start_server.py")
    
    print(f"\n💡 For detailed instructions, see: PYTHON_SETUP_GUIDE.md")

if __name__ == "__main__":
    main()
