
from datetime import datetime, timezone
from decimal import Decimal
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    ApprovalStep,
    Employee,
    LeaveRequest,
    LeaveBalance,
    ExpenseClaim,
    Reimbursement,
    AuditEvent,
)

from app.schemas.approval import ApprovalDecisionRequest


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record_audit(
    db,
    entity_type,
    entity_id,
    event_type,
    actor_id,
    before,
    after,
    details,
    now,
):
    event = AuditEvent(
        audit_event_id=f"AUD-APR-{uuid4().hex[:16].upper()}",
        entity_type=entity_type,
        entity_id=str(entity_id),
        event_type=event_type,
        actor_employee_id=actor_id,
        before_json=json.dumps(before, default=str),
        after_json=json.dumps(after, default=str),
        details_json=json.dumps(details, default=str),
        occurred_at=now,
    )

    db.add(event)


def update_leave_balance(db, request, approved):

    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == request.employee_id,
        LeaveBalance.leave_policy_id == request.leave_policy_id,
        LeaveBalance.period_year == request.start_date.year,
    ).first()

    if not balance:
        raise HTTPException(
            status_code=409,
            detail="Leave balance record not found.",
        )

    days = Decimal(str(request.business_days))
    reserved = Decimal(str(balance.pending_reserved_days))

    if reserved < days:
        raise HTTPException(
            status_code=409,
            detail="Insufficient pending leave reservation to process this decision.",
        )

    balance.pending_reserved_days = reserved - days

    if approved:
        balance.approved_used_days = (
            Decimal(str(balance.approved_used_days)) + days
        )

    balance.available_days = (
        Decimal(str(balance.opening_days))
        + Decimal(str(balance.accrued_days))
        + Decimal(str(balance.adjustment_days))
        - Decimal(str(balance.approved_used_days))
        - Decimal(str(balance.pending_reserved_days))
    )


def generate_reimbursement_id(db, year):

    prefix = f"RMB-{year}-"

    existing_ids = db.query(
        Reimbursement.reimbursement_id
    ).filter(
        Reimbursement.reimbursement_id.like(f"{prefix}%")
    ).all()

    highest_number = 0

    for (reimbursement_id,) in existing_ids:
        try:
            number = int(reimbursement_id.rsplit("-", 1)[1])
            highest_number = max(highest_number, number)
        except (ValueError, IndexError):
            continue

    return f"{prefix}{highest_number + 1:06d}"


def process_approval_decision(
    db: Session,
    approval_step_id: str,
    payload: ApprovalDecisionRequest,
):

    now = utc_now()

    try:

        # --------------------------------------
        # 1. FIND APPROVAL STEP
        # --------------------------------------

        step = db.query(ApprovalStep).filter(
            ApprovalStep.approval_step_id == approval_step_id
        ).first()

        if not step:
            raise HTTPException(
                status_code=404,
                detail="Approval step not found.",
            )

        if step.status != "pending":
            raise HTTPException(
                status_code=409,
                detail="This approval step has already been processed.",
            )

        # --------------------------------------
        # 2. VERIFY APPROVER
        # --------------------------------------

        actor = db.query(Employee).filter(
            Employee.employee_id == payload.actor_employee_id
        ).first()

        if not actor:
            raise HTTPException(
                status_code=404,
                detail="Approver employee not found.",
            )

        if actor.employment_status == "terminated":
            raise HTTPException(
                status_code=403,
                detail="A terminated employee cannot approve requests.",
            )

        if step.approver_employee_id != actor.employee_id:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to process this approval.",
            )

        # --------------------------------------
        # 3. IDENTIFY REQUEST
        # --------------------------------------

        if step.leave_request_id:

            request_type = "leave"
            entity_type = "leave_request"

            request = db.query(LeaveRequest).filter(
                LeaveRequest.leave_request_id == step.leave_request_id
            ).first()

            steps = db.query(ApprovalStep).filter(
                ApprovalStep.leave_request_id == step.leave_request_id
            ).order_by(
                ApprovalStep.step_order.asc()
            ).all()

        elif step.expense_claim_id:

            request_type = "expense"
            entity_type = "expense_claim"

            request = db.query(ExpenseClaim).filter(
                ExpenseClaim.expense_claim_id == step.expense_claim_id
            ).first()

            steps = db.query(ApprovalStep).filter(
                ApprovalStep.expense_claim_id == step.expense_claim_id
            ).order_by(
                ApprovalStep.step_order.asc()
            ).all()

        else:
            raise HTTPException(
                status_code=409,
                detail="Approval step has no associated request.",
            )

        if not request:
            raise HTTPException(
                status_code=404,
                detail="Associated request not found.",
            )

        # --------------------------------------
        # 4. CHECK REQUEST STATUS
        # --------------------------------------

        if request.status not in ("submitted", "pending_approval"):
            raise HTTPException(
                status_code=409,
                detail=f"Request cannot be processed in its current status: {request.status}",
            )

        # --------------------------------------
        # 5. ENFORCE SEQUENTIAL APPROVAL
        # --------------------------------------

        for previous_step in steps:

            if previous_step.step_order < step.step_order:

                if previous_step.status not in ("approved", "skipped"):
                    raise HTTPException(
                        status_code=409,
                        detail="Previous approval steps must be completed first.",
                    )

        step_before = {
            "status": step.status,
            "decision_reason": step.decision_reason,
        }

        request_before = {
            "status": request.status,
            "final_decision_at": request.final_decision_at,
        }

        reimbursement_id = None
        is_final = False

        # --------------------------------------
        # 6. PROCESS APPROVE
        # --------------------------------------

        if payload.decision == "approve":

            step.status = "approved"
            step.decision_reason = payload.reason or "Approved"
            step.decided_at = now

            later_pending = [
                item for item in steps
                if item.step_order > step.step_order
                and item.status == "pending"
            ]

            if later_pending:

                # More approvals are required.
                request.status = "pending_approval"

            else:

                # Final approval completed.
                is_final = True

                request.status = "approved"
                request.final_decision_at = now

                if request_type == "leave":

                    update_leave_balance(
                        db,
                        request,
                        approved=True,
                    )

                else:

                    existing = db.query(Reimbursement).filter(
                        Reimbursement.expense_claim_id
                        == request.expense_claim_id
                    ).first()

                    if existing:
                        raise HTTPException(
                            status_code=409,
                            detail="A reimbursement already exists for this claim.",
                        )

                    reimbursement_id = generate_reimbursement_id(
                        db,
                        now.year,
                    )

                    reimbursement = Reimbursement(
                        reimbursement_id=reimbursement_id,
                        expense_claim_id=request.expense_claim_id,
                        amount_minor=request.total_amount_minor,
                        currency_code=request.currency_code,
                        status="pending_payment",
                        payment_reference=None,
                        created_by_employee_id=actor.employee_id,
                        paid_at=None,
                        created_at=now,
                    )

                    db.add(reimbursement)

                    record_audit(
                        db,
                        "reimbursement",
                        reimbursement_id,
                        "reimbursement_created",
                        actor.employee_id,
                        None,
                        {
                            "status": "pending_payment",
                            "amount_minor": request.total_amount_minor,
                        },
                        {
                            "expense_claim_id": request.expense_claim_id,
                        },
                        now,
                    )

        # --------------------------------------
        # 7. PROCESS REJECT
        # --------------------------------------

        else:

            step.status = "rejected"
            step.decision_reason = payload.reason
            step.decided_at = now

            # Skip all later pending approval steps.
            for later_step in steps:

                if (
                    later_step.step_order > step.step_order
                    and later_step.status == "pending"
                ):

                    before = {
                        "status": later_step.status,
                    }

                    later_step.status = "skipped"
                    later_step.decision_reason = (
                        "Skipped because an earlier approval step rejected the request."
                    )
                    later_step.decided_at = now

                    record_audit(
                        db,
                        "approval_step",
                        later_step.approval_step_id,
                        "approval_step_skipped",
                        actor.employee_id,
                        before,
                        {
                            "status": "skipped",
                        },
                        {
                            "reason": "Earlier approval step rejected the request.",
                        },
                        now,
                    )

            request.status = "rejected"
            request.final_decision_at = now

            if request_type == "leave":

                update_leave_balance(
                    db,
                    request,
                    approved=False,
                )

            is_final = True

        # --------------------------------------
        # 8. RECORD AUDIT HISTORY
        # --------------------------------------

        step_after = {
            "status": step.status,
            "decision_reason": step.decision_reason,
        }

        request_after = {
            "status": request.status,
            "final_decision_at": request.final_decision_at,
        }

        record_audit(
            db,
            "approval_step",
            step.approval_step_id,
            f"approval_step_{payload.decision}d",
            actor.employee_id,
            step_before,
            step_after,
            {
                "request_type": request_type,
                "request_id": (
                    request.leave_request_id
                    if request_type == "leave"
                    else request.expense_claim_id
                ),
            },
            now,
        )

        if payload.decision == "reject":
            request_event = f"{request_type}_request_rejected"
        elif is_final:
            request_event = f"{request_type}_request_approved"
        else:
            request_event = f"{request_type}_approval_progressed"

        record_audit(
            db,
            entity_type,
            (
                request.leave_request_id
                if request_type == "leave"
                else request.expense_claim_id
            ),
            request_event,
            actor.employee_id,
            request_before,
            request_after,
            {
                "approval_step_id": approval_step_id,
                "decision": payload.decision,
                "reason": payload.reason,
                "reimbursement_id": reimbursement_id,
            },
            now,
        )

        # --------------------------------------
        # 9. COMMIT TRANSACTION
        # --------------------------------------

        db.commit()

        return {
            "message": "Approval decision processed successfully.",
            "approval_step_id": approval_step_id,
            "request_type": request_type,
            "request_status": request.status,
            "step_status": step.status,
            "is_final_approval": is_final,
            "reimbursement_id": reimbursement_id,
        }

    except Exception:
        db.rollback()
        raise
