
from collections import Counter

from app.db.session import SessionLocal
from app.models import Employee


# Deterministic US administrator assignments
US_ADMIN_ASSIGNMENTS = {
    "EMP-000331": {
        "role": "hr_admin",
        "department": "Human Resources",
    },
    "EMP-000338": {
        "role": "finance_admin",
        "department": "Finance",
    },
}


def ensure_country_admins():
    with SessionLocal() as session:
        try:
            for employee_id, config in US_ADMIN_ASSIGNMENTS.items():
                employee = session.get(Employee, employee_id)

                if employee is None:
                    raise ValueError(
                        f"Employee not found: {employee_id}"
                    )

                if employee.country_code != "US":
                    raise ValueError(
                        f"{employee_id} is not a US employee."
                    )

                if employee.department != config["department"]:
                    raise ValueError(
                        f"Department mismatch for {employee_id}."
                    )

                if employee.employment_status != "active":
                    raise ValueError(
                        f"{employee_id} is not active."
                    )

                if employee.system_role not in (
                    "employee",
                    config["role"],
                ):
                    raise ValueError(
                        f"Unexpected existing role for {employee_id}: "
                        f"{employee.system_role}"
                    )

                employee.system_role = config["role"]

                print(
                    f"Assigned {config['role']} to "
                    f"{employee.employee_id}"
                )

            session.flush()

            # Validate country-specific administrator coverage.
            for country in ("IN", "US"):
                for role in ("hr_admin", "finance_admin"):
                    count = (
                        session.query(Employee)
                        .filter(
                            Employee.country_code == country,
                            Employee.system_role == role,
                            Employee.employment_status == "active",
                        )
                        .count()
                    )

                    if count != 1:
                        raise ValueError(
                            f"Expected exactly one active {role} "
                            f"in {country}; found {count}."
                        )

            session.commit()

            print("\nCountry administrator validation passed!")

            employees = session.query(Employee).all()
            distribution = Counter(
                (e.country_code, e.system_role)
                for e in employees
            )

            print("\nAdministrator distribution:")
            for country in ("IN", "US"):
                print(
                    f"{country}: "
                    f"HR Admin = {distribution[(country, 'hr_admin')]}, "
                    f"Finance Admin = "
                    f"{distribution[(country, 'finance_admin')]}"
                )

        except Exception:
            session.rollback()
            raise


if __name__ == "__main__":
    ensure_country_admins()
