
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ExpenseLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_line_id: str
    expense_claim_id: str
    expense_policy_id: str
    line_number: int
    expense_date: date
    category: str
    description: str
    merchant: str
    amount_minor: int
    receipt_filename: str | None
    receipt_sha256: str | None
    receipt_mime_type: str | None
    receipt_uploaded_at: datetime | None


class ExpenseClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_claim_id: str
    employee_id: str
    cost_center_id: str | None
    country_code: str
    currency_code: str
    business_purpose: str
    expense_start_date: date
    expense_end_date: date
    primary_category: str
    total_amount_minor: int
    status: str
    submitted_at: datetime | None
    final_decision_at: datetime | None
    created_at: datetime


class ExpenseClaimDetailResponse(ExpenseClaimResponse):
    expense_lines: list[ExpenseLineResponse]


class ExpenseClaimListResponse(BaseModel):
    items: list[ExpenseClaimResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ExpenseApprovalStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_step_id: str
    expense_claim_id: str | None
    approval_rule_id: str | None

    approver_employee_id: str
    step_order: int
    status: str

    decision_reason: str | None
    assigned_at: datetime
    decided_at: datetime | None


class ReimbursementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reimbursement_id: str
    expense_claim_id: str
    amount_minor: int
    currency_code: str
    status: str
    payment_reference: str | None
    created_by_employee_id: str | None
    paid_at: datetime | None
    created_at: datetime


class ReimbursementListResponse(BaseModel):
    items: list[ReimbursementResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
