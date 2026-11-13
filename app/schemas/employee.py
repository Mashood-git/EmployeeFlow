from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: str
    first_name: str
    last_name: str
    email: str
    department: str
    job_title: str
    country_code: str
    manager_employee_id: str | None

    hire_date: date
    termination_date: date | None

    employment_status: str
    system_role: str

    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int