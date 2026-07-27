from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReschedulingProposal(Base):
    __tablename__ = "rescheduling_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'applied', 'expired')",
            name="ck_rescheduling_proposals_status",
        ),
        CheckConstraint(
            "proposal_type IN ('rollover', 'reschedule')",
            name="ck_rescheduling_proposals_type",
        ),
        CheckConstraint(
            "expected_minutes >= 0",
            name="ck_rescheduling_proposals_expected_minutes",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    proposal_type: Mapped[str] = mapped_column(String(20), default="rollover")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reason: Mapped[str] = mapped_column(Text)
    expected_minutes: Mapped[int] = mapped_column(Integer, default=0)
    deduplication_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="rescheduling_proposals")
    items: Mapped[list["ReschedulingProposalItem"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="ReschedulingProposalItem.id",
    )


class ReschedulingProposalItem(Base):
    __tablename__ = "rescheduling_proposal_items"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "daily_task_id",
            name="uq_rescheduling_proposal_task",
        ),
        CheckConstraint(
            "estimated_minutes >= 0",
            name="ck_rescheduling_proposal_items_minutes",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("rescheduling_proposals.id", ondelete="CASCADE"),
        index=True,
    )
    daily_task_id: Mapped[int] = mapped_column(
        ForeignKey("daily_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    original_date: Mapped[date] = mapped_column(Date)
    proposed_date: Mapped[date] = mapped_column(Date)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    proposal: Mapped["ReschedulingProposal"] = relationship(back_populates="items")
    daily_task: Mapped["DailyTask"] = relationship(back_populates="proposal_items")
