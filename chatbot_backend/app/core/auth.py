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
