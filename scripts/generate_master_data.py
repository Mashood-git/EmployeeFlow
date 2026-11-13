
import random
from datetime import date, datetime, timedelta

from faker import Faker

from app.db.session import SessionLocal
from app.models import Employee
from decimal import Decimal, ROUND_HALF_UP

from app.models import (
    Employee,
    LeavePolicy,
    LeaveBalance,
    EmployeeLeavePolicyAssignment,
    ExpensePolicy,
    CostCenter,
    EmployeeCostCenterAssignment,
    Holiday,
    ApprovalRule,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

SEED = 20261022
AS_OF_DATE = date(2026, 11, 11)

COUNTRY_PLAN = {
    "IN": {"total": 320, "managers": 16},
    "US": {"total": 80, "managers": 4},
}

DEPARTMENTS = [
    "Engineering",
    "Finance",
    "Human Resources",
    "Sales",
    "Operations",
    "IT",
    "Marketing",
    "Customer Support",
]

JOB_TITLES = [
    "Software Engineer",
    "Data Analyst",
    "Business Analyst",
    "QA Engineer",
    "Cloud Engineer",
    "Product Analyst",
    "HR Executive",
    "Finance Executive",
    "Operations Executive",
]

SPECIAL_ROLES = [
    "hr_admin",
    "finance_admin",
    "operations_analyst",
    "system_admin",
]

random_generator = random.Random(SEED)

fake_by_country = {
    "IN": Faker("en_IN"),
    "US": Faker("en_US"),
}

for fake in fake_by_country.values():
    fake.seed_instance(SEED)


# --------------------------------------------------
# EMPLOYEE GENERATOR
# --------------------------------------------------

def generate_employees(session):

    existing_count = session.query(Employee).count()

    if existing_count > 0:
        print(
            f"Employees already exist ({existing_count}). "
            "Skipping generation to avoid duplicates."
        )
        return

    employee_objects = []
    manager_objects = {"IN": [], "US": []}
    employee_specs = []

    employee_number = 1

    # Create employee specifications first.
    # Managers receive IDs before regular employees.

    for country_code, plan in COUNTRY_PLAN.items():

        for index in range(plan["total"]):

            is_manager = index < plan["managers"]

            employee_id = f"EMP-{employee_number:06d}"
            employee_number += 1

            employee_specs.append({
                "employee_id": employee_id,
                "country_code": country_code,
                "is_manager": is_manager,
            })

    # Create employee records.

    special_role_index = 0

    for spec in employee_specs:

        country_code = spec["country_code"]
        is_manager = spec["is_manager"]

        fake = fake_by_country[country_code]

        first_name = fake.first_name()
        last_name = fake.last_name()

        department = random_generator.choice(DEPARTMENTS)

        if is_manager:
            job_title = f"{department} Manager"
            system_role = "manager"
        else:
            job_title = random_generator.choice(JOB_TITLES)

            if special_role_index < len(SPECIAL_ROLES):
                system_role = SPECIAL_ROLES[special_role_index]
                special_role_index += 1
            else:
                system_role = "employee"

        # Generate employment dates.

        earliest_hire_date = date(2018, 1, 1)
        latest_hire_date = date(2026, 6, 30)

        hire_days = (latest_hire_date - earliest_hire_date).days

        hire_date = earliest_hire_date + timedelta(
            days=random_generator.randint(0, hire_days)
        )

        employment_status = "active"
        termination_date = None

        # Managers remain active so they can approve requests.

        if not is_manager:
            status_roll = random_generator.random()

            if status_roll < 0.03:
                employment_status = "terminated"

                available_days = (
                    AS_OF_DATE - hire_date
                ).days

                termination_date = hire_date + timedelta(
                    days=random_generator.randint(0, available_days)
                )

            elif status_roll < 0.06:
                employment_status = "on_leave"

        created_at = datetime(2026, 11, 11, 12, 0, 0)

        employee = Employee(
            employee_id=spec["employee_id"],
            first_name=first_name,
            last_name=last_name,
            email=(
                f"employee{spec['employee_id'][-6:]}"
                "@demo.employeeflow.local"
            ),
            department=department,
            job_title=job_title,
            country_code=country_code,
            manager_employee_id=None,
            hire_date=hire_date,
            termination_date=termination_date,
            employment_status=employment_status,
            system_role=system_role,
            created_at=created_at,
            updated_at=created_at,
        )

        session.add(employee)
        employee_objects.append(employee)

        if is_manager:
            manager_objects[country_code].append(employee)

    # Insert employees before assigning manager foreign keys.

    session.flush()

    # Assign managers to regular employees.
    # Every employee gets a manager from their own country.

    for employee, spec in zip(employee_objects, employee_specs):

        if spec["is_manager"]:
            continue

        available_managers = manager_objects[spec["country_code"]]

        selected_manager = random_generator.choice(
            available_managers
        )

        employee.manager_employee_id = selected_manager.employee_id

    session.commit()

    # --------------------------------------------------
    # GENERATION SUMMARY
    # --------------------------------------------------

    print("\nEmployee generation completed!")
    print("--------------------------------")

    print(f"Total employees: {len(employee_objects)}")

    for country_code in COUNTRY_PLAN:

        country_employees = [
            employee
            for employee in employee_objects
            if employee.country_code == country_code
        ]

        print(
            f"{country_code} employees: "
            f"{len(country_employees)}"
        )

    print("\nEmployment status:")

    for status in ["active", "on_leave", "terminated"]:

        count = sum(
            1
            for employee in employee_objects
            if employee.employment_status == status
        )

        print(f"{status}: {count}")

    print("\nManagers:", sum(
        len(managers)
        for managers in manager_objects.values()
    ))

    print("Employee records saved successfully!")


# --------------------------------------------------
# LEAVE MASTER DATA
# --------------------------------------------------

LEAVE_POLICY_CONFIG = {
    "IN": [
        {
            "id": "LP-IN-ANNUAL",
            "code": "IN-ANNUAL-2026",
            "name": "India Annual Leave",
            "type": "annual",
            "entitlement": 18,
            "accrual": "monthly",
            "carry_forward": 5,
            "max_consecutive": 15,
            "min_notice": 7,
        },
        {
            "id": "LP-IN-SICK",
            "code": "IN-SICK-2026",
            "name": "India Sick Leave",
            "type": "sick",
            "entitlement": 12,
            "accrual": "annual",
            "carry_forward": 0,
            "max_consecutive": 10,
            "min_notice": 0,
        },
        {
            "id": "LP-IN-CASUAL",
            "code": "IN-CASUAL-2026",
            "name": "India Casual Leave",
            "type": "casual",
            "entitlement": 8,
            "accrual": "upfront",
            "carry_forward": 0,
            "max_consecutive": 3,
            "min_notice": 1,
        },
    ],
    "US": [
        {
            "id": "LP-US-PTO",
            "code": "US-PTO-2026",
            "name": "US Paid Time Off",
            "type": "pto",
            "entitlement": 15,
            "accrual": "monthly",
            "carry_forward": 5,
            "max_consecutive": 15,
            "min_notice": 7,
        },
        {
            "id": "LP-US-SICK",
            "code": "US-SICK-2026",
            "name": "US Sick Leave",
            "type": "sick",
            "entitlement": 10,
            "accrual": "annual",
            "carry_forward": 0,
            "max_consecutive": 10,
            "min_notice": 0,
        },
        {
            "id": "LP-US-PERSONAL",
            "code": "US-PERSONAL-2026",
            "name": "US Personal Leave",
            "type": "personal",
            "entitlement": 5,
            "accrual": "upfront",
            "carry_forward": 0,
            "max_consecutive": 5,
            "min_notice": 1,
        },
    ],
}


def round_days(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def calculate_completed_months(start_date, end_date):
    months = (
        (end_date.year - start_date.year) * 12
        + end_date.month - start_date.month
    )

    if end_date.day < start_date.day:
        months -= 1

    return max(0, months)


def calculate_accrued_days(policy, start_date, end_date):

    entitlement = Decimal(
        str(policy.annual_entitlement_days)
    )

    if policy.accrual_method == "upfront":
        accrued = entitlement

    elif policy.accrual_method == "monthly":

        months = calculate_completed_months(
            start_date,
            end_date
        )

        accrued = (
            entitlement * Decimal(months) / Decimal(12)
        )

    elif policy.accrual_method == "annual":

        year_start = date(2026, 1, 1)
        year_end = date(2026, 12, 31)

        if start_date <= year_start:
            accrued = entitlement
        else:
            remaining_days = (
                year_end - start_date
            ).days + 1

            days_in_year = (
                year_end - year_start
            ).days + 1

            accrued = (
                entitlement
                * Decimal(remaining_days)
                / Decimal(days_in_year)
            )

    else:
        raise ValueError(
            f"Unsupported accrual method: "
            f"{policy.accrual_method}"
        )

    return round_days(max(Decimal("0"), accrued))


def generate_leave_master_data(session):

    # Prevent accidental duplicate generation.

    existing_data = (
        session.query(LeavePolicy).count()
        + session.query(LeaveBalance).count()
        + session.query(
            EmployeeLeavePolicyAssignment
        ).count()
    )

    if existing_data > 0:
        print(
            "\nLeave master data already exists. "
            "Skipping to prevent duplicates."
        )
        return

    employees = (
        session.query(Employee)
        .order_by(Employee.employee_id)
        .all()
    )

    if not employees:
        raise RuntimeError(
            "No employees found. Generate employees first."
        )

    policies_by_country = {
        "IN": [],
        "US": [],
    }

    # --------------------------------------------------
    # 1. CREATE LEAVE POLICIES
    # --------------------------------------------------

    for country_code, configurations in (
        LEAVE_POLICY_CONFIG.items()
    ):

        for config in configurations:

            policy = LeavePolicy(
                leave_policy_id=config["id"],
                policy_code=config["code"],
                policy_name=config["name"],
                country_code=country_code,
                leave_type=config["type"],
                annual_entitlement_days=Decimal(
                    str(config["entitlement"])
                ),
                accrual_method=config["accrual"],
                carry_forward_limit_days=Decimal(
                    str(config["carry_forward"])
                ),
                max_consecutive_days=config[
                    "max_consecutive"
                ],
                min_notice_days=config["min_notice"],
                requires_approval=True,
                effective_start_date=date(2026, 1, 1),
                effective_end_date=None,
                is_active=True,
            )

            session.add(policy)

            policies_by_country[country_code].append(
                policy
            )

    session.flush()

    # --------------------------------------------------
    # 2. CREATE ASSIGNMENTS AND LEAVE BALANCES
    # --------------------------------------------------

    assignment_count = 0
    balance_count = 0
    skipped_count = 0

    created_at = datetime(2026, 11, 11, 12, 0, 0)

    for employee in employees:

        country_policies = policies_by_country.get(
            employee.country_code,
            []
        )

        for policy_number, policy in enumerate(
            country_policies,
            start=1
        ):

            assignment_start = max(
                employee.hire_date,
                policy.effective_start_date
            )

            employment_end = (
                employee.termination_date
                or AS_OF_DATE
            )

            # Skip employees whose employment ended
            # before this policy became effective.

            if employment_end < assignment_start:
                skipped_count += 1
                continue

            assignment = EmployeeLeavePolicyAssignment(
                employee_id=employee.employee_id,
                leave_policy_id=policy.leave_policy_id,
                effective_from=assignment_start,
                effective_to=employee.termination_date,
                is_active=(
                    employee.employment_status != "terminated"
                ),
                created_at=created_at,
            )

            session.add(assignment)
            assignment_count += 1

            # Calculate accrual only up to the
            # employee's last employment date or today.

            accrual_end = min(
                AS_OF_DATE,
                employment_end
            )

            accrued_days = calculate_accrued_days(
                policy,
                assignment_start,
                accrual_end
            )

            opening_days = Decimal("0.00")
            adjustment_days = Decimal("0.00")
            approved_used_days = Decimal("0.00")
            pending_reserved_days = Decimal("0.00")

            available_days = (
                opening_days
                + accrued_days
                + adjustment_days
                - approved_used_days
                - pending_reserved_days
            )

            balance = LeaveBalance(
                leave_balance_id=(
                    f"LB-{employee.employee_id[-6:]}-"
                    f"{policy_number:02d}"
                ),
                employee_id=employee.employee_id,
                leave_policy_id=policy.leave_policy_id,
                period_year=2026,
                opening_days=opening_days,
                accrued_days=accrued_days,
                adjustment_days=adjustment_days,
                approved_used_days=approved_used_days,
                pending_reserved_days=pending_reserved_days,
                available_days=round_days(available_days),
                as_of_date=AS_OF_DATE,
            )

            session.add(balance)
            balance_count += 1

    session.commit()

    # --------------------------------------------------
    # 3. GENERATION SUMMARY
    # --------------------------------------------------

    print("\nLeave master data generated successfully!")
    print("------------------------------------------")

    print(
        "Leave policies:",
        session.query(LeavePolicy).count()
    )

    print("Employee assignments:", assignment_count)
    print("Leave balances:", balance_count)
    print("Skipped assignments:", skipped_count)

    print("\nPolicies by country:")

    for country_code, policies in policies_by_country.items():
        print(f"{country_code}: {len(policies)} policies")

    print("\nLeave master data saved successfully!")



# --------------------------------------------------
# EXPENSE MASTER DATA CONFIGURATION
# --------------------------------------------------

# All monetary values are in minor units:
# INR: 100 paise = 1 rupee
# USD: 100 cents = 1 dollar
#
# Tuple format:
# (per_item, daily, claim, receipt_threshold, approval_threshold)

EXPENSE_POLICY_CONFIG = {
    "IN": {
        "currency": "INR",
        "categories": {
            "travel": (5_000_000, 1_000_000, 10_000_000, 10_000, 1_000_000),
            "meals": (250_000, 500_000, 1_500_000, 50_000, 200_000),
            "accommodation": (1_000_000, 1_200_000, 5_000_000, 50_000, 800_000),
            "office_supplies": (1_500_000, 1_500_000, 3_000_000, 100_000, 300_000),
            "software": (5_000_000, 5_000_000, 10_000_000, 100_000, 1_500_000),
            "training": (3_000_000, 3_000_000, 6_000_000, 50_000, 500_000),
        },
        "budgets": {
            "Engineering": 50_000_000,
            "Finance": 20_000_000,
            "Human Resources": 15_000_000,
            "Sales": 40_000_000,
            "Operations": 30_000_000,
            "IT": 35_000_000,
            "Marketing": 25_000_000,
            "Customer Support": 20_000_000,
        },
    },

    "US": {
        "currency": "USD",
        "categories": {
            "travel": (500_000, 100_000, 1_000_000, 10_000, 100_000),
            "meals": (25_000, 50_000, 150_000, 5_000, 15_000),
            "accommodation": (100_000, 120_000, 500_000, 5_000, 80_000),
            "office_supplies": (150_000, 150_000, 300_000, 10_000, 30_000),
            "software": (500_000, 500_000, 1_000_000, 10_000, 150_000),
            "training": (300_000, 300_000, 600_000, 5_000, 50_000),
        },
        "budgets": {
            "Engineering": 10_000_000,
            "Finance": 4_000_000,
            "Human Resources": 3_000_000,
            "Sales": 8_000_000,
            "Operations": 6_000_000,
            "IT": 7_000_000,
            "Marketing": 5_000_000,
            "Customer Support": 4_000_000,
        },
    },
}

DEPARTMENT_CODES = {
    "Engineering": "ENG",
    "Finance": "FIN",
    "Human Resources": "HR",
    "Sales": "SALES",
    "Operations": "OPS",
    "IT": "IT",
    "Marketing": "MKT",
    "Customer Support": "SUP",
}

CATEGORY_CODES = {
    "travel": "TRV",
    "meals": "MEAL",
    "accommodation": "ACC",
    "office_supplies": "OFF",
    "software": "SW",
    "training": "TRN",
}

COMPANY_HOLIDAYS = {
    "IN": [
        (date(2026, 1, 1), "New Year's Day"),
        (date(2026, 1, 26), "Republic Day"),
        (date(2026, 5, 1), "Labour Day"),
        (date(2026, 8, 15), "Independence Day"),
        (date(2026, 10, 2), "Gandhi Jayanti"),
        (date(2026, 12, 25), "Christmas Day"),
    ],
    "US": [
        (date(2026, 1, 1), "New Year's Day"),
        (date(2026, 1, 19), "Martin Luther King Jr. Day"),
        (date(2026, 5, 25), "Memorial Day"),
        (date(2026, 7, 3), "Independence Day Observed"),
        (date(2026, 9, 7), "Labor Day"),
        (date(2026, 11, 26), "Thanksgiving Day"),
        (date(2026, 12, 25), "Christmas Day"),
    ],
}


# --------------------------------------------------
# EXPENSE MASTER DATA GENERATOR
# --------------------------------------------------

def generate_expense_master_data(session):

    # Prevent duplicate generation.

    existing_data = (
        session.query(ExpensePolicy).count()
        + session.query(CostCenter).count()
        + session.query(EmployeeCostCenterAssignment).count()
        + session.query(Holiday).count()
        + session.query(ApprovalRule).count()
    )

    if existing_data > 0:
        print(
            "\nExpense master data already exists. "
            "Skipping to prevent duplicates."
        )
        return

    employees = (
        session.query(Employee)
        .order_by(Employee.employee_id)
        .all()
    )

    if not employees:
        raise RuntimeError(
            "No employees found. Generate employees first."
        )

    policy_count = 0
    cost_center_count = 0
    assignment_count = 0
    skipped_assignments = 0
    holiday_count = 0
    approval_rule_count = 0

    cost_centers = {}

    effective_date = date(2026, 1, 1)

    # --------------------------------------------------
    # 1. CREATE EXPENSE POLICIES
    # --------------------------------------------------

    approval_thresholds = {}

    for country_code, config in EXPENSE_POLICY_CONFIG.items():

        currency_code = config["currency"]

        for category, limits in config["categories"].items():

            (
                per_item,
                daily,
                claim,
                receipt_threshold,
                approval_threshold,
            ) = limits

            policy = ExpensePolicy(
                expense_policy_id=(
                    f"EP-{country_code}-{category.upper()}"
                ),
                policy_code=(
                    f"{country_code}-{category.upper()}-2026"
                ),
                policy_name=(
                    f"{category.replace('_', ' ').title()} Expense Policy"
                ),
                country_code=country_code,
                category=category,
                currency_code=currency_code,
                per_item_limit_minor=per_item,
                daily_limit_minor=daily,
                claim_limit_minor=claim,
                receipt_required=True,
                receipt_threshold_minor=receipt_threshold,
                effective_start_date=effective_date,
                effective_end_date=None,
                is_active=True,
            )

            session.add(policy)
            policy_count += 1

            approval_thresholds[
                (country_code, category)
            ] = approval_threshold

    # --------------------------------------------------
    # 2. CREATE COST CENTERS
    # --------------------------------------------------

    for country_code, config in EXPENSE_POLICY_CONFIG.items():

        currency_code = config["currency"]

        for department, department_code in DEPARTMENT_CODES.items():

            cost_center = CostCenter(
                cost_center_id=(
                    f"CC-{country_code}-{department_code}"
                ),
                cost_center_code=(
                    f"{country_code}-{department_code}-2026"
                ),
                cost_center_name=(
                    f"{department} Cost Center"
                ),
                country_code=country_code,
                currency_code=currency_code,
                budget_amount_minor=config["budgets"][department],
                effective_start_date=effective_date,
                effective_end_date=None,
                is_active=True,
            )

            session.add(cost_center)

            cost_centers[
                (country_code, department)
            ] = cost_center

            cost_center_count += 1

    # Ensure expense policies and cost centers
    # are inserted before dependent records.

    session.flush()

    # --------------------------------------------------
    # 3. ASSIGN EMPLOYEES TO COST CENTERS
    # --------------------------------------------------

    for employee in employees:

        key = (
            employee.country_code,
            employee.department
        )

        cost_center = cost_centers.get(key)

        if cost_center is None:
            raise ValueError(
                f"No cost center found for employee "
                f"{employee.employee_id}: {key}"
            )

        assignment_start = max(
            employee.hire_date,
            effective_date
        )

        employment_end = (
            employee.termination_date
            or AS_OF_DATE
        )

        if employment_end < assignment_start:
            skipped_assignments += 1
            continue

        assignment = EmployeeCostCenterAssignment(
            employee_id=employee.employee_id,
            cost_center_id=cost_center.cost_center_id,
            effective_from=assignment_start,
            effective_to=employee.termination_date,
            is_primary=True,
        )

        # assignment_id is INTEGER and auto-generated.

        session.add(assignment)
        assignment_count += 1

    # --------------------------------------------------
    # 4. CREATE COMPANY HOLIDAYS
    # --------------------------------------------------

    for country_code, holidays in COMPANY_HOLIDAYS.items():

        for holiday_date, holiday_name in holidays:

            holiday = Holiday(
                country_code=country_code,
                holiday_date=holiday_date,
                holiday_name=holiday_name,
                is_optional=False,
            )

            # holiday_id is INTEGER and auto-generated.

            session.add(holiday)
            holiday_count += 1

    # --------------------------------------------------
    # 5. CREATE APPROVAL RULES
    # --------------------------------------------------

    def add_approval_rule(
        rule_id,
        rule_set_code,
        rule_name,
        request_type,
        country_code,
        category,
        min_amount,
        max_amount,
        min_leave_days,
        max_leave_days,
        approver_type,
        approver_role,
        step_order,
    ):

        nonlocal approval_rule_count

        rule = ApprovalRule(
            approval_rule_id=rule_id,
            rule_set_code=rule_set_code,
            rule_name=rule_name,
            request_type=request_type,
            country_code=country_code,
            category=category,
            min_amount_minor=min_amount,
            max_amount_minor=max_amount,
            min_leave_days=min_leave_days,
            max_leave_days=max_leave_days,
            priority=10,
            approver_type=approver_type,
            approver_role=approver_role,
            approver_employee_id=None,
            step_order=step_order,
            effective_start_date=effective_date,
            effective_end_date=None,
            is_active=True,
        )

        session.add(rule)
        approval_rule_count += 1

    # --------------------------------------------------
    # 5A. LEAVE APPROVAL RULES
    # --------------------------------------------------

    for country_code in ["IN", "US"]:

        # Short leave: manager approval only.

        add_approval_rule(
            rule_id=f"AR-{country_code}-L-SHORT",
            rule_set_code=f"{country_code}-LEAVE-SHORT",
            rule_name="Leave up to 5 days - Manager Approval",
            request_type="leave",
            country_code=country_code,
            category=None,
            min_amount=None,
            max_amount=None,
            min_leave_days=1,
            max_leave_days=5,
            approver_type="manager",
            approver_role=None,
            step_order=1,
        )

        # Long leave: manager approval, step 1.

        add_approval_rule(
            rule_id=f"AR-{country_code}-L-LONG-M",
            rule_set_code=f"{country_code}-LEAVE-LONG",
            rule_name="Long Leave - Manager Approval",
            request_type="leave",
            country_code=country_code,
            category=None,
            min_amount=None,
            max_amount=None,
            min_leave_days=6,
            max_leave_days=None,
            approver_type="manager",
            approver_role=None,
            step_order=1,
        )

        # Long leave: HR approval, step 2.

        add_approval_rule(
            rule_id=f"AR-{country_code}-L-LONG-HR",
            rule_set_code=f"{country_code}-LEAVE-LONG",
            rule_name="Long Leave - HR Approval",
            request_type="leave",
            country_code=country_code,
            category=None,
            min_amount=None,
            max_amount=None,
            min_leave_days=6,
            max_leave_days=None,
            approver_type="role",
            approver_role="hr_admin",
            step_order=2,
        )

    # --------------------------------------------------
    # 5B. EXPENSE APPROVAL RULES
    # --------------------------------------------------

    for country_code, config in EXPENSE_POLICY_CONFIG.items():

        for category in config["categories"]:

            category_code = CATEGORY_CODES[category]

            threshold = approval_thresholds[
                (country_code, category)
            ]

            # Low amount: manager approval only.

            low_rule_set = (
                f"{country_code}-EXP-{category_code}-LOW"
            )

            add_approval_rule(
                rule_id=f"AR-{country_code}-E-{category_code}-L",
                rule_set_code=low_rule_set,
                rule_name=(
                    f"{category.title()} - Standard Manager Approval"
                ),
                request_type="expense",
                country_code=country_code,
                category=category,
                min_amount=0,
                max_amount=threshold,
                min_leave_days=None,
                max_leave_days=None,
                approver_type="manager",
                approver_role=None,
                step_order=1,
            )

            # High amount: manager approval, step 1.

            high_rule_set = (
                f"{country_code}-EXP-{category_code}-HIGH"
            )

            add_approval_rule(
                rule_id=f"AR-{country_code}-E-{category_code}-HM",
                rule_set_code=high_rule_set,
                rule_name=(
                    f"{category.title()} - High Value Manager Approval"
                ),
                request_type="expense",
                country_code=country_code,
                category=category,
                min_amount=threshold + 1,
                max_amount=None,
                min_leave_days=None,
                max_leave_days=None,
                approver_type="manager",
                approver_role=None,
                step_order=1,
            )

            # High amount: finance approval, step 2.

            add_approval_rule(
                rule_id=f"AR-{country_code}-E-{category_code}-HF",
                rule_set_code=high_rule_set,
                rule_name=(
                    f"{category.title()} - High Value Finance Approval"
                ),
                request_type="expense",
                country_code=country_code,
                category=category,
                min_amount=threshold + 1,
                max_amount=None,
                min_leave_days=None,
                max_leave_days=None,
                approver_type="role",
                approver_role="finance_admin",
                step_order=2,
            )

    # --------------------------------------------------
    # 6. SAVE ALL EXPENSE MASTER DATA
    # --------------------------------------------------

    session.commit()

    # --------------------------------------------------
    # 7. GENERATION SUMMARY
    # --------------------------------------------------

    print("\nExpense master data generated successfully!")
    print("---------------------------------------------")

    print("Expense policies:", policy_count)
    print("Cost centers:", cost_center_count)
    print("Employee cost center assignments:", assignment_count)
    print("Skipped cost center assignments:", skipped_assignments)
    print("Company holidays:", holiday_count)
    print("Approval rules:", approval_rule_count)

    print("\nExpense policies by country:")

    for country_code, config in EXPENSE_POLICY_CONFIG.items():
        print(
            f"{country_code}: "
            f"{len(config['categories'])} policies"
        )

    print("\nExpense master data saved successfully!")



def ensure_country_admins(session):
    """
    Ensure each country has its own HR and Finance administrator.
    Uses deterministic employee IDs.
    """

    assignments = {
        "EMP-000017": ("IN", "hr_admin"),
        "EMP-000018": ("IN", "finance_admin"),
        "EMP-000331": ("US", "hr_admin"),
        "EMP-000338": ("US", "finance_admin"),
    }

    for employee_id, (country, role) in assignments.items():
        employee = session.get(Employee, employee_id)

        if employee is None:
            raise ValueError(
                f"Administrator employee not found: {employee_id}"
            )

        if employee.country_code != country:
            raise ValueError(
                f"Country mismatch for {employee_id}"
            )

        if employee.employment_status != "active":
            raise ValueError(
                f"Administrator {employee_id} is not active"
            )

        employee.system_role = role

    session.flush()

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
                    f"Expected one {role} in {country}; found {count}"
                )

    session.commit()
    print("Country-specific administrators validated!")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    session = SessionLocal()

    try:
        generate_employees(session)
        ensure_country_admins(session)
        generate_leave_master_data(session)
        generate_expense_master_data(session)

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
