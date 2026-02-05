
import sys
from pathlib import Path

# Add chatbot_backend to sys.path
backend_path = Path("c:/Users/nivin/Documents/Chatbot_RAG_System_UI_1/chatbot_backend")
sys.path.append(str(backend_path))

from app.core.database import SessionLocal, init_database
from app.models.user import User
from app.config import settings

def check_users():
    try:
        init_database()
        db = SessionLocal()
        users = db.query(User).all()
        print(f"Total users found: {len(users)}")
        for user in users:
            print(f"User: {user.username}, Role: {user.role}, Active: {user.is_active}")
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_users()
