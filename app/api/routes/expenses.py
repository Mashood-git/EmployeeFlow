
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    ExpenseClaim,
    ExpenseLine,
    ApprovalStep,
    Reimbursement,
    )
from app.schemas.expense import (
    ExpenseClaimListResponse,
    ExpenseClaimResponse,
    ExpenseClaimDetailResponse,
    ExpenseLineResponse,
    ExpenseApprovalStepResponse,
    ReimbursementListResponse,
)


router = APIRouter()


@router.get(
    "/claims",
    response_model=ExpenseClaimListResponse
)
def list_expense_claims(
    employee_id: str | None = None,
    status: str | None = None,
    country_code: str | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ExpenseClaim)

    # Filter by employee
    if employee_id:
        query = query.filter(
            ExpenseClaim.employee_id == employee_id
        )

    # Filter by claim status
    if status:
        query = query.filter(
            ExpenseClaim.status == status
        )

    # Filter by country
    if country_code:
        query = query.filter(
            ExpenseClaim.country_code == country_code.upper()
        )

    # Filter by expense category
    if category:
        query = query.filter(
            ExpenseClaim.primary_category == category.lower()
        )

    # Count matching records before pagination
    total = query.count()

    # Fetch the requested page
    items = (
        query
        .order_by(
            ExpenseClaim.created_at.desc(),
            ExpenseClaim.expense_claim_id.asc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (
        (total + page_size - 1) // page_size
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get(
    "/claims/{claim_id}",
    response_model=ExpenseClaimDetailResponse
)
def get_expense_claim(
    claim_id: str,
    db: Session = Depends(get_db),
):
    # Find the expense claim
    claim = (
        db.query(ExpenseClaim)
        .filter(
            ExpenseClaim.expense_claim_id == claim_id
        )
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Expense claim not found"
        )

    # Retrieve all expense lines in line-number order
    expense_lines = (
        db.query(ExpenseLine)
        .filter(
            ExpenseLine.expense_claim_id == claim_id
        )
        .order_by(ExpenseLine.line_number.asc())
        .all()
    )

    # Convert claim and expense lines into response data
    claim_data = ExpenseClaimResponse.model_validate(
        claim
    ).model_dump()

    claim_data["expense_lines"] = [
        ExpenseLineResponse.model_validate(line).model_dump()
        for line in expense_lines
    ]

    return claim_data


@router.get(
    "/claims/{claim_id}/approvals",
    response_model=list[ExpenseApprovalStepResponse]
)
def get_expense_approval_history(
    claim_id: str,
    db: Session = Depends(get_db),
):
    claim = (
        db.query(ExpenseClaim)
        .filter(
            ExpenseClaim.expense_claim_id == claim_id
        )
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Expense claim not found"
        )

    approval_steps = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.expense_claim_id == claim_id
        )
        .order_by(ApprovalStep.step_order.asc())
        .all()
    )

    return approval_steps


@router.get(
    "/reimbursements",
    response_model=ReimbursementListResponse
)
def list_reimbursements(
    employee_id: str | None = None,
    status: str | None = None,
    country_code: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Reimbursement)
        .join(
            ExpenseClaim,
            Reimbursement.expense_claim_id
            == ExpenseClaim.expense_claim_id
        )
    )

    # Filter by employee
    if employee_id:
        query = query.filter(
            ExpenseClaim.employee_id == employee_id
        )

    # Filter by reimbursement status
    if status:
        query = query.filter(
            Reimbursement.status == status
        )

    # Filter by country
    if country_code:
        query = query.filter(
            ExpenseClaim.country_code == country_code.upper()
        )

    # Count matching reimbursements
    total = query.count()

    # Fetch the requested page
    items = (
        query
        .order_by(
            Reimbursement.created_at.desc(),
            Reimbursement.reimbursement_id.asc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (
        (total + page_size - 1) // page_size
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
