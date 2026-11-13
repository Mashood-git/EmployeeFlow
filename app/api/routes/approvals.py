
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.schemas.approval import ApprovalDecisionRequest
from app.services.approval_service import process_approval_decision

from app.db.session import get_db
from app.models import (
    ApprovalStep,
    Employee,
    LeaveRequest,
    LeavePolicy,
    ExpenseClaim,
)

router = APIRouter()


@router.get("/pending")
def get_pending_approvals(
    approver_employee_id: str | None = None,
    request_type: Literal["leave", "expense"] | None = None,
    country_code: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(ApprovalStep).filter(
        ApprovalStep.status == "pending"
    )

    if approver_employee_id:
        query = query.filter(
            ApprovalStep.approver_employee_id == approver_employee_id.upper()
        )

    steps = query.order_by(
        ApprovalStep.assigned_at.asc(),
        ApprovalStep.step_order.asc(),
    ).all()

    results = []

    for step in steps:

        # ---------------------------------
        # LEAVE APPROVAL
        # ---------------------------------

        if step.leave_request_id:

            if request_type == "expense":
                continue

            request = db.query(LeaveRequest).filter(
                LeaveRequest.leave_request_id == step.leave_request_id
            ).first()

            if not request:
                continue

            employee = db.query(Employee).filter(
                Employee.employee_id == request.employee_id
            ).first()

            if not employee:
                continue

            if country_code and employee.country_code.upper() != country_code.upper():
                continue

            policy = db.query(LeavePolicy).filter(
                LeavePolicy.leave_policy_id == request.leave_policy_id
            ).first()

            results.append({
                "approval_step_id": step.approval_step_id,
                "request_type": "leave",
                "request_id": request.leave_request_id,
                "requester_employee_id": employee.employee_id,
                "requester_name": f"{employee.first_name} {employee.last_name}",
                "department": employee.department,
                "country_code": employee.country_code,
                "approver_employee_id": step.approver_employee_id,
                "step_order": step.step_order,
                "status": step.status,
                "assigned_at": step.assigned_at,
                "request_status": request.status,
                "summary": policy.leave_type if policy else "Leave Request",
                "start_date": request.start_date,
                "end_date": request.end_date,
                "business_days": float(request.business_days),
                "amount_minor": None,
                "currency_code": None,
                "category": None,
                "business_purpose": None,
            })

        # ---------------------------------
        # EXPENSE APPROVAL
        # ---------------------------------

        elif step.expense_claim_id:

            if request_type == "leave":
                continue

            claim = db.query(ExpenseClaim).filter(
                ExpenseClaim.expense_claim_id == step.expense_claim_id
            ).first()

            if not claim:
                continue

            employee = db.query(Employee).filter(
                Employee.employee_id == claim.employee_id
            ).first()

            if not employee:
                continue

            if country_code and employee.country_code.upper() != country_code.upper():
                continue

            results.append({
                "approval_step_id": step.approval_step_id,
                "request_type": "expense",
                "request_id": claim.expense_claim_id,
                "requester_employee_id": employee.employee_id,
                "requester_name": f"{employee.first_name} {employee.last_name}",
                "department": employee.department,
                "country_code": employee.country_code,
                "approver_employee_id": step.approver_employee_id,
                "step_order": step.step_order,
                "status": step.status,
                "assigned_at": step.assigned_at,
                "request_status": claim.status,
                "summary": claim.business_purpose,
                "start_date": claim.expense_start_date,
                "end_date": claim.expense_end_date,
                "business_days": None,
                "amount_minor": claim.total_amount_minor,
                "currency_code": claim.currency_code,
                "category": claim.primary_category,
                "business_purpose": claim.business_purpose,
            })

    return {
        "total": len(results),
        "items": results,
    }


# --------------------------------------------------
# APPROVAL DECISION HISTORY
# --------------------------------------------------

@router.get("/history")
def get_approval_history(
    approver_employee_id: str | None = None,
    request_type: Literal["leave", "expense"] | None = None,
    country_code: str | None = None,
    decision_status: Literal[
        "approved", "rejected", "skipped"
    ] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(ApprovalStep).filter(
        ApprovalStep.status.in_(
            ["approved", "rejected", "skipped"]
        )
    )

    if approver_employee_id:
        query = query.filter(
            ApprovalStep.approver_employee_id
            == approver_employee_id.strip().upper()
        )

    if decision_status:
        query = query.filter(
            ApprovalStep.status == decision_status
        )

    steps = query.order_by(
        ApprovalStep.decided_at.desc(),
        ApprovalStep.assigned_at.desc(),
    ).all()

    results = []

    for step in steps:

        approver = db.query(Employee).filter(
            Employee.employee_id == step.approver_employee_id
        ).first()

        # LEAVE APPROVAL HISTORY
        if step.leave_request_id:

            if request_type == "expense":
                continue

            request = db.query(LeaveRequest).filter(
                LeaveRequest.leave_request_id == step.leave_request_id
            ).first()

            if not request:
                continue

            employee = db.query(Employee).filter(
                Employee.employee_id == request.employee_id
            ).first()

            if not employee:
                continue

            if (
                country_code
                and employee.country_code.upper() != country_code.upper()
            ):
                continue

            policy = db.query(LeavePolicy).filter(
                LeavePolicy.leave_policy_id == request.leave_policy_id
            ).first()

            results.append({
                "approval_step_id": step.approval_step_id,
                "request_type": "leave",
                "request_id": request.leave_request_id,
                "requester_employee_id": employee.employee_id,
                "requester_name": (
                    f"{employee.first_name} {employee.last_name}"
                ),
                "department": employee.department,
                "country_code": employee.country_code,
                "approver_employee_id": step.approver_employee_id,
                "approver_name": (
                    f"{approver.first_name} {approver.last_name}"
                    if approver else "Unknown"
                ),
                "step_order": step.step_order,
                "decision": step.status,
                "decision_reason": step.decision_reason,
                "assigned_at": step.assigned_at,
                "decided_at": step.decided_at,
                "request_status": request.status,
                "summary": policy.leave_type if policy else "Leave Request",
                "start_date": request.start_date,
                "end_date": request.end_date,
                "business_days": float(request.business_days),
                "amount_minor": None,
                "currency_code": None,
                "category": None,
            })

        # EXPENSE APPROVAL HISTORY
        elif step.expense_claim_id:

            if request_type == "leave":
                continue

            claim = db.query(ExpenseClaim).filter(
                ExpenseClaim.expense_claim_id == step.expense_claim_id
            ).first()

            if not claim:
                continue

            employee = db.query(Employee).filter(
                Employee.employee_id == claim.employee_id
            ).first()

            if not employee:
                continue

            if (
                country_code
                and employee.country_code.upper() != country_code.upper()
            ):
                continue

            results.append({
                "approval_step_id": step.approval_step_id,
                "request_type": "expense",
                "request_id": claim.expense_claim_id,
                "requester_employee_id": employee.employee_id,
                "requester_name": (
                    f"{employee.first_name} {employee.last_name}"
                ),
                "department": employee.department,
                "country_code": employee.country_code,
                "approver_employee_id": step.approver_employee_id,
                "approver_name": (
                    f"{approver.first_name} {approver.last_name}"
                    if approver else "Unknown"
                ),
                "step_order": step.step_order,
                "decision": step.status,
                "decision_reason": step.decision_reason,
                "assigned_at": step.assigned_at,
                "decided_at": step.decided_at,
                "request_status": claim.status,
                "summary": claim.business_purpose,
                "start_date": claim.expense_start_date,
                "end_date": claim.expense_end_date,
                "business_days": None,
                "amount_minor": claim.total_amount_minor,
                "currency_code": claim.currency_code,
                "category": claim.primary_category,
            })

        if len(results) >= limit:
            break

    return {
        "total": len(results),
        "items": results,
    }



@router.post("/{approval_step_id}/decision")
def submit_approval_decision(
    approval_step_id: str,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
):
    return process_approval_decision(
        db=db,
        approval_step_id=approval_step_id,
        payload=payload,
    )