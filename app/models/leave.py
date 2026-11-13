
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LeavePolicy(Base):

    __tablename__ = "leave_policies"

    __table_args__ = (
        CheckConstraint(
            "annual_entitlement_days >= 0",
            name="ck_leave_policy_entitlement",
        ),
        CheckConstraint(
            "carry_forward_limit_days >= 0",
            name="ck_leave_policy_carry_forward",
        ),
        CheckConstraint(
            "min_notice_days >= 0",
            name="ck_leave_policy_notice",
        ),
        CheckConstraint(
            "accrual_method IN ('monthly', 'annual', 'upfront')",
            name="ck_leave_policy_accrual",
        ),
        CheckConstraint(
            "effective_end_date IS NULL OR "
            "effective_end_date >= effective_start_date",
            name="ck_leave_policy_dates",
        ),
    )

    leave_policy_id: Mapped[str] = mapped_column(
        String(20), primary_key=True
    )

    policy_code: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )

    policy_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False
    )

    leave_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    annual_entitlement_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )

    accrual_method: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False
    )

    carry_forward_limit_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    max_consecutive_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    min_notice_days: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    requires_approval: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    effective_start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    effective_end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    balances: Mapped[list["LeaveBalance"]] = relationship(
        "LeaveBalance",
        back_populates="leave_policy",
    )
    
    requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest",
        back_populates="leave_policy",
    )


class LeaveBalance(Base):

    __tablename__ = "leave_balances"

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "leave_policy_id",
            "period_year",
            name="uq_leave_balance_employee_policy_year",
        ),
        CheckConstraint(
            "opening_days >= 0 AND accrued_days >= 0 "
            "AND approved_used_days >= 0 "
            "AND pending_reserved_days >= 0",
            name="ck_leave_balance_nonnegative",
        ),
    )

    leave_balance_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=False,
    )

    leave_policy_id: Mapped[str] = mapped_column(
        ForeignKey("leave_policies.leave_policy_id"),
        nullable=False,
    )

    period_year: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    opening_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    accrued_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    adjustment_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    approved_used_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    pending_reserved_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    available_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("0.00"), nullable=False
    )

    as_of_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="leave_balances",
    )

    leave_policy: Mapped["LeavePolicy"] = relationship(
        "LeavePolicy",
        back_populates="balances",
    )


class LeaveRequest(Base):

    __tablename__ = "leave_requests"

    __table_args__ = (
        CheckConstraint(
            "start_date <= end_date",
            name="ck_leave_request_date_order",
        ),
        CheckConstraint(
            "business_days >= 0",
            name="ck_leave_request_business_days",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'pending_approval', "
            "'needs_review', 'approved', 'rejected', 'cancelled')",
            name="ck_leave_request_status",
        ),
    )

    leave_request_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=False,
    )

    leave_policy_id: Mapped[str] = mapped_column(
        ForeignKey("leave_policies.leave_policy_id"),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    end_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    business_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )

    reason: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(25), default="draft", nullable=False
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    final_decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="leave_requests",
    )

    leave_policy: Mapped["LeavePolicy"] = relationship(
        "LeavePolicy",
        back_populates="requests",
    )

    approval_steps: Mapped[list["ApprovalStep"]] = relationship(
        "ApprovalStep",
        back_populates="leave_request",
    )