
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Employee, ExpenseClaim
from app.services.exception_service import detect_exceptions

router = APIRouter()


@router.get("/breakdown")
def get_analytics_breakdown(
    db: Session = Depends(get_db)
):
    # 1. Workforce distribution by country
    country_rows = (
        db.query(
            Employee.country_code,
            func.count(Employee.employee_id).label("employee_count"),
        )
        .group_by(Employee.country_code)
        .order_by(Employee.country_code)
        .all()
    )

    workforce_by_country = [
        {
            "country_code": row.country_code,
            "employee_count": int(row.employee_count),
        }
        for row in country_rows
    ]

    # 2. Workforce distribution by department
    department_rows = (
        db.query(
            Employee.department,
            func.count(Employee.employee_id).label("employee_count"),
        )
        .group_by(Employee.department)
        .order_by(Employee.department)
        .all()
    )

    workforce_by_department = [
        {
            "department": row.department,
            "employee_count": int(row.employee_count),
        }
        for row in department_rows
    ]

    # 3. Actual approved expense spend by department
    expense_rows = (
        db.query(
            Employee.department,
            ExpenseClaim.country_code,
            ExpenseClaim.currency_code,
            func.count(
                ExpenseClaim.expense_claim_id
            ).label("claim_count"),
            func.coalesce(
                func.sum(ExpenseClaim.total_amount_minor), 0
            ).label("total_amount_minor"),
        )
        .join(
            Employee,
            Employee.employee_id == ExpenseClaim.employee_id,
        )
        .filter(ExpenseClaim.status == "approved")
        .group_by(
            Employee.department,
            ExpenseClaim.country_code,
            ExpenseClaim.currency_code,
        )
        .order_by(
            Employee.department,
            ExpenseClaim.country_code,
            ExpenseClaim.currency_code,
        )
        .all()
    )

    approved_expenses_by_department = [
        {
            "department": row.department,
            "country_code": row.country_code,
            "currency_code": row.currency_code,
            "claim_count": int(row.claim_count),
            "total_amount_minor": int(row.total_amount_minor),
        }
        for row in expense_rows
    ]

    # 4. Exception distribution
    exception_items = detect_exceptions(db)

    type_counts = Counter(
        item["exception_type"] for item in exception_items
    )

    severity_counts = Counter(
        item["severity"] for item in exception_items
    )

    exceptions_by_type = [
        {
            "exception_type": exception_type,
            "count": count,
        }
        for exception_type, count in sorted(type_counts.items())
    ]

    exceptions_by_severity = [
        {
            "severity": severity,
            "count": count,
        }
        for severity, count in sorted(severity_counts.items())
    ]

    return {
        "workforce_by_country": workforce_by_country,
        "workforce_by_department": workforce_by_department,
        "approved_expenses_by_department": approved_expenses_by_department,
        "exception_summary": {
            "total_findings": len(exception_items),
            "by_type": exceptions_by_type,
            "by_severity": exceptions_by_severity,
        },
    }
