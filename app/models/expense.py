
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
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
# 1. EXPENSE POLICY
# ==========================================

class ExpensePolicy(Base):

    __tablename__ = "expense_policies"

    __table_args__ = (
        CheckConstraint(
            "per_item_limit_minor IS NULL OR per_item_limit_minor >= 0",
            name="ck_expense_policy_item_limit",
        ),
        CheckConstraint(
            "daily_limit_minor IS NULL OR daily_limit_minor >= 0",
            name="ck_expense_policy_daily_limit",
        ),
        CheckConstraint(
            "claim_limit_minor IS NULL OR claim_limit_minor >= 0",
            name="ck_expense_policy_claim_limit",
        ),
        CheckConstraint(
            "effective_end_date IS NULL OR "
            "effective_end_date >= effective_start_date",
            name="ck_expense_policy_dates",
        ),
    )

    expense_policy_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    policy_code: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False
    )

    policy_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False
    )

    per_item_limit_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    daily_limit_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    claim_limit_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    receipt_required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    receipt_threshold_minor: Mapped[int | None] = mapped_column(
        Integer, nullable=True
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

    expense_lines: Mapped[list["ExpenseLine"]] = relationship(
        "ExpenseLine",
        back_populates="expense_policy",
    )


# ==========================================
# 2. COST CENTER
# ==========================================

class CostCenter(Base):

    __tablename__ = "cost_centers"

    __table_args__ = (
        CheckConstraint(
            "budget_amount_minor >= 0",
            name="ck_cost_center_budget",
        ),
        CheckConstraint(
            "effective_end_date IS NULL OR "
            "effective_end_date >= effective_start_date",
            name="ck_cost_center_dates",
        ),
    )

    cost_center_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    cost_center_code: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False
    )

    cost_center_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False
    )

    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False
    )

    budget_amount_minor: Mapped[int] = mapped_column(
        Integer, nullable=False
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

    expense_claims: Mapped[list["ExpenseClaim"]] = relationship(
        "ExpenseClaim",
        back_populates="cost_center",
    )


# ==========================================
# 3. EXPENSE CLAIM
# ==========================================

class ExpenseClaim(Base):

    __tablename__ = "expense_claims"

    __table_args__ = (
        CheckConstraint(
            "expense_start_date <= expense_end_date",
            name="ck_expense_claim_date_order",
        ),
        CheckConstraint(
            "total_amount_minor >= 0",
            name="ck_expense_claim_total",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'pending_approval', "
            "'needs_review', 'approved', 'rejected', 'cancelled')",
            name="ck_expense_claim_status",
        ),
    )

    expense_claim_id: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=False,
    )

    cost_center_id: Mapped[str | None] = mapped_column(
        ForeignKey("cost_centers.cost_center_id"),
        nullable=True,
    )

    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False
    )

    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False
    )

    business_purpose: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    expense_start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    expense_end_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    primary_category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    total_amount_minor: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
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
        back_populates="expense_claims",
    )

    cost_center: Mapped["CostCenter | None"] = relationship(
        "CostCenter",
        back_populates="expense_claims",
    )

    expense_lines: Mapped[list["ExpenseLine"]] = relationship(
        "ExpenseLine",
        back_populates="expense_claim",
    )
    
    approval_steps: Mapped[list["ApprovalStep"]] = relationship(
        "ApprovalStep",
        back_populates="expense_claim",
    )

    reimbursement: Mapped["Reimbursement | None"] = relationship(
        "Reimbursement",
        back_populates="expense_claim",
        uselist=False,
    )


# ==========================================
# 4. EXPENSE LINE
# ==========================================

class ExpenseLine(Base):

    __tablename__ = "expense_lines"

    __table_args__ = (
        UniqueConstraint(
            "expense_claim_id",
            "line_number",
            name="uq_expense_line_number",
        ),
        CheckConstraint(
            "line_number >= 1",
            name="ck_expense_line_number",
        ),
        CheckConstraint(
            "amount_minor > 0",
            name="ck_expense_line_amount",
        ),
    )

    expense_line_id: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )

    expense_claim_id: Mapped[str] = mapped_column(
        ForeignKey("expense_claims.expense_claim_id"),
        nullable=False,
    )

    expense_policy_id: Mapped[str] = mapped_column(
        ForeignKey("expense_policies.expense_policy_id"),
        nullable=False,
    )

    line_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    expense_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    merchant: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    amount_minor: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    receipt_filename: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    receipt_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    receipt_mime_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    receipt_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    expense_claim: Mapped["ExpenseClaim"] = relationship(
        "ExpenseClaim",
        back_populates="expense_lines",
    )

    expense_policy: Mapped["ExpensePolicy"] = relationship(
        "ExpensePolicy",
        back_populates="expense_lines",
    )
