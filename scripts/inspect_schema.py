
import app.models

from app.db.base import Base


def inspect_schema():
    print("\n========== EMPLOYEEFLOW DATABASE SCHEMA ==========\n")

    for table in Base.metadata.tables.values():
        print(f"\nTABLE: {table.name}")
        print("-" * 60)

        for column in table.columns:
            foreign_keys = [
                fk.target_fullname for fk in column.foreign_keys
            ]

            print(
                f"  {column.name:<30} "
                f"Type: {str(column.type):<20} "
                f"Nullable: {column.nullable} "
                f"Primary Key: {column.primary_key}"
            )

            if foreign_keys:
                print(f"      Foreign Key: {', '.join(foreign_keys)}")

    print("\n========== SCHEMA INSPECTION COMPLETE ==========")


if __name__ == "__main__":
    inspect_schema()
