'''
    Normally, Python tries to evaluate type annotations immediately.If User is not defined yet, Python may raise an error.
    But with it, Python does not immediately evaluate the annotation.It treats annotations more lazily, almost like strings.
    It helps Python handle type hints that refer to classes before they are fully defined.This is common in SQLAlchemy models because models often reference each other.
    In this project,It makes model-to-model references easier and avoids some circular import / undefined-name problems.
    Important rule: This line must be at the top of the file, before normal imports
'''
from __future__ import annotations

from datetime import date, datetime


from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

'''
    SQLAlchemy lets you define database tables as Python classes.It is the bridge between your Python backend and your database.
    This style is called ORM(Object Relational Mapper).
    it maps:
        Python object  <->  Database row
        Python class   <->  Database table
        Class attribute <-> Database column纵
    Common SQLAlchemy parts:
        Base is the parent class for your database models.It tells SQLAlchemy this class represents a database table.
        Columns are defined using mapped_column, which specifies the column type and constraints. e.g.email = Column(String, unique=True, nullable=False)
        A session is the object used to talk to the database. e.g. to add, update, delete, or query data.

'''
class DailyReview(Base):
    __tablename__ = "daily_reviews"

    # defines extra rules for the table
    __table_args__ = (
        # One user can only have one daily review per date
        UniqueConstraint("user_id", "review_date", name="uq_daily_reviews_user_date"),
        CheckConstraint(
            "planned_tasks >= 0 AND completed_tasks >= 0 AND focus_minutes >= 0",
            name="ck_daily_reviews_nonnegative_stats",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 创建数据库外键列: stores the related user's id in the database
    # index=True: This makes searching by user_id faster.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    review_date: Mapped[date] = mapped_column(Date, index=True)

    # uses Text can store long text
    summary: Mapped[str] = mapped_column(Text)
    tomorrow_adjustment: Mapped[str | None] = mapped_column(Text)
    planned_tasks: Mapped[int] = mapped_column(default=0)
    completed_tasks: Mapped[int] = mapped_column(default=0)
    focus_minutes: Mapped[int] = mapped_column(default=0)
    source: Mapped[str] = mapped_column(String(20), default="ai")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 创建Python 对象关系: gives you the related User object in Python(对于每个对象DailyReview，SQLAlchemy 都能找到相关的User对象)
    '''
        Why "User" has quotes? This is a forward reference: the User class may be defined later or imported in a way that would otherwise cause a circular reference
        meaning: "User" means the User class, but Python does not need to resolve it immediately
        back_populates="daily_reviews" means It connects this relationship with the matching relationship inside the User model
    '''
    user: Mapped["User"] = relationship(back_populates="daily_reviews")
