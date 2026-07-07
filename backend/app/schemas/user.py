from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class UserLogin(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
