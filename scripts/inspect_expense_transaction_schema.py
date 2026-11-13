from app.models import (
    ExpenseClaim,
    ExpenseLine,
    Reimbursement,
    ApprovalStep,
    AuditEvent,
    EmployeeCostCenterAssignment
)

models = [
    ExpenseClaim,
    ExpenseLine,
    Reimbursement,
    ApprovalStep,
    AuditEvent,
    EmployeeCostCenterAssignment
]

for model in models:
    print(f"\n{'=' * 60}")
    print(model.__name__.upper())
    print(f"{'=' * 60}")

    for column in model.__table__.columns:
        print(
            f"{column.name:<30} "
            f"type={str(column.type):<20} "
            f"nullable={column.nullable} "
            f"primary_key={column.primary_key}"
        )
