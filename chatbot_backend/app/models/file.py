# app/models/file.py

from pydantic import BaseModel
from datetime import datetime

class FileMeta(BaseModel):
    file_id: str
    file_name: str
    uploaded_by: str
    uploaded_at: datetime = None

    class Config:
        orm_mode = True
