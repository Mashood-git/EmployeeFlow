from __future__ import annotations
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Employee(Base):

    __tablename__ = "employees"

    __table_args__ = (
        CheckConstraint(
            "employment_status IN ('active', 'on_leave', 'terminated')",
            name="ck_employees_employment_status",
        ),
        CheckConstraint(
            "system_role IN ('employee', 'manager', 'hr_admin', "
            "'finance_admin', 'operations_analyst', 'system_admin')",
            name="ck_employees_system_role",
        ),
        CheckConstraint(
            "termination_date IS NULL OR termination_date >= hire_date",
            name="ck_employees_termination_after_hire",
        ),
    )

    # Primary key
    employee_id: Mapped[str] = mapped_column(
        String(20), primary_key=True
    )

    # Personal information
    first_name: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    last_name: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )

    # Professional information
    department: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    job_title: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False
    )

    # Manager relationship
    manager_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )

    manager: Mapped[Employee | None] = relationship(
        "Employee",
        remote_side="Employee.employee_id",
        back_populates="direct_reports",
    )

    direct_reports: Mapped[list[Employee]] = relationship(
        "Employee",
        back_populates="manager",
    )

    # Employment details
    hire_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    termination_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    employment_status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )

    system_role: Mapped[str] = mapped_column(
        String(30), default="employee", nullable=False
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship with leave balances
    leave_balances: Mapped[list] = relationship(
        "LeaveBalance",
        back_populates="employee",
    )


    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest",
        back_populates="employee",
    )
    
    expense_claims: Mapped[list["ExpenseClaim"]] = relationship(
        "ExpenseClaim",
        back_populates="employee",
    )

    approval_steps: Mapped[list["ApprovalStep"]] = relationship(
        "ApprovalStep",
        back_populates="approver",
    )

    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="actor",
    )