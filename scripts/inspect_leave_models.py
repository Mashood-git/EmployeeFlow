
from app.models import (
    LeavePolicy,
    LeaveBalance,
    EmployeeLeavePolicyAssignment,
    Holiday,
)

models = [
    LeavePolicy,
    LeaveBalance,
    EmployeeLeavePolicyAssignment,
    Holiday,
]

for model in models:
    print(f"\n{'=' * 50}")
    print(f"MODEL: {model.__name__}")
    print("=" * 50)

    for column in model.__table__.columns:
        print(
            f"{column.name} | "
            f"{column.type} | "
            f"Nullable: {column.nullable}"
        )
