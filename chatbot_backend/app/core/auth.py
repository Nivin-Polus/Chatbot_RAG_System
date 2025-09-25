# app/core/auth.py

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
import jwt
import logging
from sqlalchemy.orm import Session
# FastAPI dependencies are in app.core.permissions

from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing context (using bcrypt for MySQL compatibility)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Hash a plain password
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# Verify a plain password against hashed password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# Create a JWT access token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user against MySQL database"""
    try:
        from app.core.database import get_db
        from app.models.user import User
        
        # Get database session
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Find user by username
            user = db.query(User).filter(User.username == username, User.is_active == True).first()
            
            if not user:
                logger.warning(f"Authentication failed: User '{username}' not found or inactive")
                return None
            
            # Verify password
            if not verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password for user '{username}'")
                return None
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()
            
            logger.info(f"✅ User '{username}' authenticated successfully")
            
            return {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        return None


def validate_credentials(username: str, password: str) -> bool:
    """Validate user credentials against MySQL database"""
    user = authenticate_user(username, password)
    return user is not None


def get_token_from_credentials(username: str, password: str) -> Optional[str]:
    """Generate token if credentials are valid"""
    try:
        if not username or not password:
            return None
        
        user = authenticate_user(username, password)
        if not user:
            return None
        
        # Create token with user information
        token_data = {
            "sub": user["username"],
            "user_id": user["user_id"],
            "role": user["role"],
            "email": user["email"]
        }
        
        access_token = create_access_token(data=token_data)
        return access_token
        
    except Exception as e:
        logger.error(f"❌ Token generation error: {e}")
        return None


def get_current_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Get current user information from JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            return None
        
        # Get fresh user data from database
        from app.core.database import get_db
        from app.models.user import User
        
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            user = db.query(User).filter(User.username == username, User.is_active == True).first()
            
            if user is None:
                return None
            
            return {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active
            }
            
        finally:
            db.close()
            
    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ User validation error: {e}")
        return None


def create_user(username: str, password: str, email: str = None, full_name: str = None, role: str = "user") -> Optional[Dict[str, Any]]:
    """Create a new user in the database"""
    try:
        from app.core.database import get_db
        from app.models.user import User
        
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                logger.warning(f"User creation failed: Username '{username}' already exists")
                return None
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                full_name=full_name,
                role=role,
                is_active=True
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            logger.info(f"✅ User '{username}' created successfully")
            
            return {
                "user_id": new_user.user_id,
                "username": new_user.username,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role,
                "is_active": new_user.is_active
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ User creation error: {e}")
        return None


# Note: get_current_user FastAPI dependency is defined in app.core.permissions
