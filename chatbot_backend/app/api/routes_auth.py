# app/api/routes_auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from pydantic import BaseModel

from app.config import settings
from app.models.user import User
from app.core.auth import verify_password, get_password_hash, create_access_token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# For MVP: in-memory users (replace with DB in production)
fake_users_db = {
    "admin": {
        "username": "admin",
        "password_hash": get_password_hash("admin123"),
        "role": "admin"
    },
    "user": {
        "username": "user",
        "password_hash": get_password_hash("user123"),
        "role": "user"
    }
}

# Login endpoint
@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(form_data.password, user_dict["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_dict["username"], "role": user_dict["role"]}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "role": user_dict["role"]}


# Dependency to get current user from JWT
async def get_current_user(token: str = Depends(oauth2_scheme)):
    import jwt
    from jwt import InvalidTokenError

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": role}
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
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    # Get current user data
    user_dict = fake_users_db.get(current_user["username"])
    if not user_dict:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not verify_password(request.current_password, user_dict["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Validate new password
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long")
    
    # Update password
    new_password_hash = get_password_hash(request.new_password)
    fake_users_db[current_user["username"]]["password_hash"] = new_password_hash
    
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
