from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LeaveBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    leave_balance_id: str
    employee_id: str
    leave_policy_id: str
    period_year: int

    opening_days: Decimal
    accrued_days: Decimal
    adjustment_days: Decimal
    approved_used_days: Decimal
    pending_reserved_days: Decimal
    available_days: Decimal

    as_of_date: date


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    leave_request_id: str
    employee_id: str
    leave_policy_id: str

    start_date: date
    end_date: date
    business_days: Decimal

    reason: str | None
    status: str

    submitted_at: datetime | None
    final_decision_at: datetime | None
    created_at: datetime


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    
class LeaveApprovalStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_step_id: str
    leave_request_id: str | None
    approval_rule_id: str | None

    approver_employee_id: str
    step_order: int
    status: str

    decision_reason: str | None
    assigned_at: datetime
    decided_at: datetime | None