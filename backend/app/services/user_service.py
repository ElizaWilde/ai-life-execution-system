from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import UserUpdate


class DuplicateUserEmailError(ValueError):
    pass


class UserService:
    def update(self, db: Session, user: User, payload: UserUpdate) -> User:
        data = payload.model_dump(exclude_unset=True)
        email = data.get("email")
        if email is not None:
            normalized_email = email.strip().lower()
            duplicate = db.scalar(
                select(User.id).where(
                    User.email == normalized_email,
                    User.id != user.id,
                )
            )
            if duplicate is not None:
                raise DuplicateUserEmailError("Email is already in use")
            data["email"] = normalized_email

        if "display_name" in data and data["display_name"] is not None:
            data["display_name"] = data["display_name"].strip()

        for field, value in data.items():
            setattr(user, field, value)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DuplicateUserEmailError("Email is already in use") from exc
        db.refresh(user)
        return user


user_service = UserService()
