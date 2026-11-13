import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Employee,
    LeaveBalance,
    LeaveRequest,
    ApprovalStep,
    )

from app.schemas.leave import (
    LeaveBalanceResponse,
    LeaveRequestResponse,
    LeaveRequestListResponse,
    LeaveApprovalStepResponse,
)

router = APIRouter()


# 1. Get leave balances for an employee
@router.get(
    "/balances/{employee_id}",
    response_model=list[LeaveBalanceResponse]
)
def get_leave_balances(
    employee_id: str,
    db: Session = Depends(get_db)
):
    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == employee_id)
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )

    balances = (
        db.query(LeaveBalance)
        .filter(LeaveBalance.employee_id == employee_id)
        .order_by(
            LeaveBalance.period_year.desc(),
            LeaveBalance.leave_policy_id
        )
        .all()
    )

    return balances


# 2. List and filter leave requests
@router.get(
    "/requests",
    response_model=LeaveRequestListResponse
)
def get_leave_requests(
    employee_id: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):

    query = db.query(LeaveRequest)

    if employee_id:
        query = query.filter(
            LeaveRequest.employee_id == employee_id
        )

    if status:
        query = query.filter(
            LeaveRequest.status == status.strip().lower()
        )

    total = query.count()

    requests = (
        query
        .order_by(LeaveRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total / page_size) if total else 0

    return LeaveRequestListResponse(
        items=requests,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


# 3. Get one specific leave request
@router.get(
    "/requests/{leave_request_id}",
    response_model=LeaveRequestResponse
)
def get_leave_request(
    leave_request_id: str,
    db: Session = Depends(get_db)
):

    leave_request = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.leave_request_id == leave_request_id
        )
        .first()
    )

    if not leave_request:
        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )

    return leave_request

@router.get(
    "/requests/{leave_request_id}/approvals",
    response_model=list[LeaveApprovalStepResponse]
)
def get_leave_approval_history(
    leave_request_id: str,
    db: Session = Depends(get_db)
):
    leave_request = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.leave_request_id == leave_request_id
        )
        .first()
    )

    if not leave_request:
        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )

    approval_steps = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.leave_request_id == leave_request_id
        )
        .order_by(ApprovalStep.step_order.asc())
        .all()
    )

    return approval_steps