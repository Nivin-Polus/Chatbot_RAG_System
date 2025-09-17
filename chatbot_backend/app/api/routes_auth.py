# app/api/routes_auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta

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
