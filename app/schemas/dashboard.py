from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_employees: int
    active_employees: int

    total_leave_requests: int
    pending_leave_requests: int
    leave_requests_needs_review: int
    approved_leave_requests: int
    rejected_leave_requests: int

    total_expense_claims: int
    pending_expense_claims: int
    expense_claims_needs_review: int
    approved_expense_claims: int
    rejected_expense_claims: int

    total_reimbursements: int
    pending_reimbursements: int
    paid_reimbursements: int