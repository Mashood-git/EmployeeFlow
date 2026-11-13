
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditEvent(Base):

    __tablename__ = "audit_events"

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('employee', 'leave_request', "
            "'expense_claim', 'approval_step', 'reimbursement', "
            "'leave_policy', 'expense_policy')",
            name="ck_audit_event_entity_type",
        ),
    )

    audit_event_id: Mapped[str] = mapped_column(
        String(40), primary_key=True
    )

    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    entity_id: Mapped[str] = mapped_column(
        String(70), nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(60), nullable=False
    )

    actor_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=True,
    )

    before_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    after_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    details_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    actor: Mapped["Employee | None"] = relationship(
        "Employee",
        back_populates="audit_events",
    )
