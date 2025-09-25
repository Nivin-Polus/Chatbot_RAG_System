# app/api/routes_auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.core.auth import verify_password, get_password_hash, create_access_token
from app.core.database import get_db

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Login endpoint - now uses MySQL database
@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Get user from database
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Update last login
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username, 
            "role": user.role,
            "user_id": user.user_id,
            "website_id": user.website_id
        }, 
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "role": user.role,
        "username": user.username,
        "website_id": user.website_id,
        "user_id": user.user_id
    }


# Dependency to get current user from JWT
async def get_current_user(token: str = Depends(oauth2_scheme)):
    import jwt
    from jwt import InvalidTokenError

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: str = payload.get("user_id")
        website_id: str = payload.get("website_id")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        return {
            "username": username, 
            "role": role,
            "user_id": user_id,
            "website_id": website_id
        }
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Password change request model
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

# Change password endpoint
@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    # Get current user from database
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Validate new password
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long")
    
    # Update password in database
    user.password_hash = get_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

# Verify token endpoint
@router.get("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify if the current JWT token is valid"""
    return {
        "valid": True,
        "user": current_user["username"],
        "role": current_user["role"]
    }
