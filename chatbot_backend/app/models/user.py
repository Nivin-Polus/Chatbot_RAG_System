# app/models/user.py

from pydantic import BaseModel

class User(BaseModel):
    username: str
    password: str
