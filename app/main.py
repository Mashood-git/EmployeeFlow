from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.employees import router as employees_router
from app.api.routes.leave import router as leave_router
from app.api.routes.expenses import router as expenses_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.exceptions import router as exceptions_router
from app.api.routes.analytics import router as analytics_router

app = FastAPI(
    title="EmployeeFlow API",
    description="Intelligent Leave and Expense Management System",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "application": "EmployeeFlow",
        "status": "running",
        "api_docs": "/docs"
    }


app.include_router(
    health_router,
    prefix="/api/v1"
)

app.include_router(
    dashboard_router,
    prefix="/api/v1/dashboard"
)

app.include_router(
    employees_router,
    prefix="/api/v1/employees",
    tags=["Employees"]
)

app.include_router(
    leave_router,
    prefix="/api/v1/leave",
    tags=["Leave Management"]
)

app.include_router(
    expenses_router,
    prefix="/api/v1/expenses",
    tags=["Expense Management"]
)

app.include_router(
    approvals_router,
    prefix="/api/v1/approvals",
    tags=["Approval Center"]
)

app.include_router(
    exceptions_router,
    prefix="/api/v1/exceptions",
    tags=["Exception Management"]
)

app.include_router(
    analytics_router,
    prefix="/api/v1/analytics",
    tags=["Analytics"]
)
