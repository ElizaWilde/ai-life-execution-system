from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    x_user_id: Annotated[int, Header(alias="X-User-ID", gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Temporary single-header identity until JWT authentication is implemented."""
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )
    return user
