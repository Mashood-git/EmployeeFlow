from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Employee,
    LeaveRequest,
    ExpenseClaim,
    Reimbursement,
)
from app.schemas.dashboard import DashboardSummary

router = APIRouter()


def get_count(db: Session, model, *conditions) -> int:
    query = db.query(func.count()).select_from(model)

    if conditions:
        query = query.filter(*conditions)

    return int(query.scalar() or 0)


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):

    return DashboardSummary(
        total_employees=get_count(db, Employee),

        active_employees=get_count(
            db, Employee,
            Employee.employment_status == "active"
        ),

        total_leave_requests=get_count(db, LeaveRequest),

        pending_leave_requests=get_count(
            db, LeaveRequest,
            LeaveRequest.status.in_(["submitted", "pending_approval"])
        ),

        leave_requests_needs_review=get_count(
            db, LeaveRequest,
            LeaveRequest.status == "needs_review"
        ),

        approved_leave_requests=get_count(
            db, LeaveRequest,
            LeaveRequest.status == "approved"
        ),

        rejected_leave_requests=get_count(
            db, LeaveRequest,
            LeaveRequest.status == "rejected"
        ),

        total_expense_claims=get_count(db, ExpenseClaim),

        pending_expense_claims=get_count(
            db, ExpenseClaim,
            ExpenseClaim.status.in_(["submitted", "pending_approval"])
        ),

        expense_claims_needs_review=get_count(
            db, ExpenseClaim,
            ExpenseClaim.status == "needs_review"
        ),

        approved_expense_claims=get_count(
            db, ExpenseClaim,
            ExpenseClaim.status == "approved"
        ),

        rejected_expense_claims=get_count(
            db, ExpenseClaim,
            ExpenseClaim.status == "rejected"
        ),

        total_reimbursements=get_count(db, Reimbursement),

        pending_reimbursements=get_count(
            db, Reimbursement,
            Reimbursement.status == "pending_payment"
        ),

        paid_reimbursements=get_count(
            db, Reimbursement,
            Reimbursement.status == "paid"
        ),
    )