from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Reimbursement(Base):

    __tablename__ = "reimbursements"

    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="ck_reimbursement_amount",
        ),
        CheckConstraint(
            "status IN ('pending_payment', 'paid', 'failed', 'cancelled')",
            name="ck_reimbursement_status",
        ),
    )

    reimbursement_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    expense_claim_id: Mapped[str] = mapped_column(
        ForeignKey("expense_claims.expense_claim_id"),
        unique=True,
        nullable=False,
    )

    amount_minor: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(25), default="pending_payment", nullable=False
    )

    payment_reference: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )

    created_by_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expense_claim: Mapped["ExpenseClaim"] = relationship(
        "ExpenseClaim",
        back_populates="reimbursement",
    )