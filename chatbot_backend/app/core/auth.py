# app/core/auth.py

from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
import jwt

from app.config import settings

# Password hashing context (using argon2 instead of bcrypt to avoid Rust dependencies)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


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

def validate_credentials(username: str, password: str) -> bool:
    """Validate user credentials against configured values"""
    return (username == settings.API_USERNAME and 
            verify_password(password, settings.API_PASSWORD_HASH))

def get_token_from_credentials(username: str, password: str) -> Optional[str]:
    """Generate token if credentials are valid"""
    try:
        if not username or not password:
            return None
            
        if validate_credentials(username, password):
            access_token = create_access_token(
                data={"sub": username}
            )
            return access_token
        return None
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return None
