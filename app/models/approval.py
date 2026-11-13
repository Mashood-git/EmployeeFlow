
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

from app.db.base import Base


# ==========================================
# 1. APPROVAL RULE
# ==========================================

class ApprovalRule(Base):

    __tablename__ = "approval_rules"

    __table_args__ = (
        CheckConstraint(
            "request_type IN ('leave', 'expense')",
            name="ck_approval_rule_request_type",
        ),
        CheckConstraint(
            "approver_type IN ('manager', 'role', 'employee')",
            name="ck_approval_rule_approver_type",
        ),
        CheckConstraint(
            "step_order >= 1 AND priority >= 1",
            name="ck_approval_rule_order_priority",
        ),
        CheckConstraint(
            "(min_amount_minor IS NULL OR min_amount_minor >= 0) "
            "AND (max_amount_minor IS NULL OR max_amount_minor >= 0) "
            "AND (min_amount_minor IS NULL OR max_amount_minor IS NULL "
            "OR max_amount_minor >= min_amount_minor)",
            name="ck_approval_rule_amount_range",
        ),
        CheckConstraint(
            "(min_leave_days IS NULL OR min_leave_days >= 0) "
            "AND (max_leave_days IS NULL OR max_leave_days >= 0) "
            "AND (min_leave_days IS NULL OR max_leave_days IS NULL "
            "OR max_leave_days >= min_leave_days)",
            name="ck_approval_rule_leave_range",
        ),
        CheckConstraint(
            "effective_end_date IS NULL OR "
            "effective_end_date >= effective_start_date",
            name="ck_approval_rule_dates",
        ),
        CheckConstraint(
            "(approver_type = 'manager' AND approver_role IS NULL "
            "AND approver_employee_id IS NULL) OR "
            "(approver_type = 'role' AND approver_role IS NOT NULL "
            "AND approver_employee_id IS NULL) OR "
            "(approver_type = 'employee' AND approver_employee_id IS NOT NULL "
            "AND approver_role IS NULL)",
            name="ck_approval_rule_approver_target",
        ),
    )

    approval_rule_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    rule_set_code: Mapped[str] = mapped_column(
        String(40), nullable=False
    )

    rule_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    request_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    country_code: Mapped[str | None] = mapped_column(
        String(2), nullable=True
    )

    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    min_amount_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    max_amount_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    min_leave_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    max_leave_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    priority: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )

    approver_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    approver_role: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    approver_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=True,
    )

    step_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    effective_start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    effective_end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    specific_approver: Mapped["Employee | None"] = relationship(
        "Employee",
        foreign_keys=[approver_employee_id],
    )

    approval_steps: Mapped[list["ApprovalStep"]] = relationship(
        "ApprovalStep",
        back_populates="approval_rule",
    )


# ==========================================
# 2. APPROVAL STEP
# ==========================================

class ApprovalStep(Base):

    __tablename__ = "approval_steps"

    __table_args__ = (
        CheckConstraint(
            "(leave_request_id IS NOT NULL AND expense_claim_id IS NULL) "
            "OR (leave_request_id IS NULL AND expense_claim_id IS NOT NULL)",
            name="ck_approval_step_exactly_one_request",
        ),
        CheckConstraint(
            "step_order >= 1",
            name="ck_approval_step_order",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'skipped')",
            name="ck_approval_step_status",
        ),
        UniqueConstraint(
            "leave_request_id",
            "step_order",
            name="uq_leave_approval_step_order",
        ),
        UniqueConstraint(
            "expense_claim_id",
            "step_order",
            name="uq_expense_approval_step_order",
        ),
    )

    approval_step_id: Mapped[str] = mapped_column(
        String(70), primary_key=True
    )

    leave_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("leave_requests.leave_request_id"),
        nullable=True,
    )

    expense_claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("expense_claims.expense_claim_id"),
        nullable=True,
    )

    approval_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("approval_rules.approval_rule_id"),
        nullable=True,
    )

    approver_employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=False,
    )

    step_order: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    leave_request: Mapped["LeaveRequest | None"] = relationship(
        "LeaveRequest",
        back_populates="approval_steps",
    )

    expense_claim: Mapped["ExpenseClaim | None"] = relationship(
        "ExpenseClaim",
        back_populates="approval_steps",
    )

    approval_rule: Mapped["ApprovalRule | None"] = relationship(
        "ApprovalRule",
        back_populates="approval_steps",
    )

    approver: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="approval_steps",
    )
