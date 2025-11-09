from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional

# Each model corresponds to a collection name (lowercased)
class Visit(BaseModel):
    path: str = "/"
    user_agent: Optional[str] = None

class Stat(BaseModel):
    total_visits: int

class Contacts(BaseModel):
    instagram: Optional[HttpUrl] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    x: Optional[HttpUrl] = None
