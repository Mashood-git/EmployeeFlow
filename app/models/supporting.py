
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmployeeLeavePolicyAssignment(Base):
    __tablename__ = "employee_leave_policy_assignments"

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "leave_policy_id",
            "effective_from",
            name="uq_employee_leave_policy_start",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_employee_leave_policy_dates",
        ),
    )

    assignment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    leave_policy_id: Mapped[str] = mapped_column(
        ForeignKey("leave_policies.leave_policy_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class EmployeeCostCenterAssignment(Base):
    __tablename__ = "employee_cost_center_assignments"

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "cost_center_id",
            "effective_from",
            name="uq_employee_cost_center_start",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_employee_cost_center_dates",
        ),
    )

    assignment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.cost_center_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class Holiday(Base):
    __tablename__ = "holidays"

    __table_args__ = (
        UniqueConstraint(
            "country_code",
            "holiday_date",
            "holiday_name",
            name="uq_country_holiday",
        ),
    )

    holiday_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False, index=True
    )

    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)

    holiday_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    is_optional: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
