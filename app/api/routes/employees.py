import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Employee
from app.schemas.employee import (
    EmployeeResponse,
    EmployeeListResponse,
)

router = APIRouter()


@router.get("", response_model=EmployeeListResponse)
def get_employees(
    search: str | None = Query(default=None, max_length=100),
    country: str | None = None,
    department: str | None = None,
    employment_status: str | None = None,
    system_role: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Employee)

    # Search employees
    if search and search.strip():
        search_term = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Employee.employee_id.ilike(search_term),
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.email.ilike(search_term),
                Employee.department.ilike(search_term),
                Employee.job_title.ilike(search_term),
            )
        )

    # Country filter
    if country:
        query = query.filter(
            Employee.country_code == country.strip().upper()
        )

    # Department filter
    if department:
        query = query.filter(
            Employee.department.ilike(department.strip())
        )

    # Employment status filter
    if employment_status:
        query = query.filter(
            Employee.employment_status == employment_status.strip().lower()
        )

    # System role filter
    if system_role:
        query = query.filter(
            Employee.system_role == system_role.strip().lower()
        )

    # Count matching employees
    total = query.count()

    # Pagination and sorting
    employees = (
        query
        .order_by(Employee.employee_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total / page_size) if total else 0

    return EmployeeListResponse(
        items=employees,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: str,
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == employee_id)
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    return employee