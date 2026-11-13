
import app.models

from sqlalchemy import CheckConstraint, UniqueConstraint
from app.db.base import Base


def inspect_constraints():
    print("\n========== DATABASE CONSTRAINTS ==========\n")

    for table in Base.metadata.sorted_tables:
        print(f"\nTABLE: {table.name}")

        for constraint in table.constraints:

            if isinstance(constraint, CheckConstraint):
                print("  CHECK:", {constraint.sqltext.text})

            elif isinstance(constraint, UniqueConstraint):
                columns = ", ".join(
                    column.name for column in constraint.columns
                )
                print(f"  UNIQUE: {columns}")

    print("\n========== INSPECTION COMPLETE ==========")


if __name__ == "__main__":
    inspect_constraints()
