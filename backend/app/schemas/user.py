"""User schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserResponse(BaseModel):
    """Response schema for user data."""

    id: int
    email: EmailStr
    name: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}
