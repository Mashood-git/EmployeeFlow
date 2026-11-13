"""Generate deterministic EmployeeFlow expense transactions.

Run from the EmployeeFlow project root:
    python -m scripts.generate_expense_transactions

The script refuses to run if expense transaction data already exists.
It does not modify leave requests, leave balances, or leave audit events.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.db.session import SessionLocal
from app.models import (
    ApprovalRule,
    ApprovalStep,
    AuditEvent,
    CostCenter,
    Employee,
    EmployeeCostCenterAssignment,
    ExpenseClaim,
    ExpenseLine,
    ExpensePolicy,
    Reimbursement,
)


SEED = 20261022
YEAR = 2026
START_DATE = date(2026, 1, 1)
AS_OF_DATE = date(2026, 11, 11)
MAX_DATETIME = datetime.combine(AS_OF_DATE, time(23, 59, 0))
TARGET_CLAIMS = 1000

STATUS_WEIGHTS = {
    "draft": 5,
    "submitted": 8,
    "pending_approval": 20,
    "needs_review": 5,
    "approved": 42,
    "rejected": 12,
    "cancelled": 8,
}

REIMBURSEMENT_STATUS_WEIGHTS = {
    "pending_payment": 25,
    "paid": 65,
    "failed": 10,
}

MERCHANTS = {
    "travel": ["IndiGo", "Air India", "United Airlines", "Uber", "Ola", "IRCTC"],
    "meals": ["Cafe Coffee Day", "Starbucks", "Domino's", "Local Restaurant", "Food Court"],
    "accommodation": ["Taj Hotels", "Marriott", "Hilton", "Treebo", "OYO"],
    "office_supplies": ["Staples", "Office Depot", "Amazon Business", "Local Stationery"],
    "software": ["Microsoft", "Atlassian", "JetBrains", "Adobe", "AWS"],
    "training": ["Coursera", "Udemy", "Pluralsight", "Training Institute"],
}

DESCRIPTIONS = {
    "travel": "Business travel and local transportation",
    "meals": "Business meeting meal expense",
    "accommodation": "Business trip accommodation",
    "office_supplies": "Office equipment and supplies",
    "software": "Business software subscription or license",
    "training": "Professional development and training",
}

BUSINESS_PURPOSES = {
    "travel": "Client visit and business meetings",
    "meals": "Customer meeting and team discussion",
    "accommodation": "Accommodation during an approved business trip",
    "office_supplies": "Department operational requirements",
    "software": "Software required for department operations",
    "training": "Role-related professional development",
}


def as_json(value) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def clamp_datetime(value: datetime) -> datetime:
    return min(value, MAX_DATETIME)


def random_datetime(rng: random.Random, day: date, start_hour: int = 9) -> datetime:
    hour = rng.randint(start_hour, 18)
    minute = rng.choice([0, 10, 15, 20, 30, 40, 45, 50])
    return datetime.combine(day, time(hour, minute))


def distribute_amount(total: int, count: int, per_line_cap: int, rng: random.Random) -> list[int]:
    """Split a positive integer total into count positive values under the cap."""
    if count < 1 or total < count or total > count * per_line_cap:
        raise ValueError(
            f"Cannot distribute total={total} into count={count} lines with cap={per_line_cap}"
        )

    values: list[int] = []
    remaining = total
    for index in range(count):
        slots_after = count - index - 1
        minimum = max(1, remaining - slots_after * per_line_cap)
        maximum = min(per_line_cap, remaining - slots_after)
        amount = remaining if slots_after == 0 else rng.randint(minimum, maximum)
        values.append(amount)
        remaining -= amount
    return values


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def active_on_day(record, start_attr: str, end_attr: str, day: date) -> bool:
    start = getattr(record, start_attr)
    end = getattr(record, end_attr)
    return start <= day and (end is None or end >= day)


def build_policy_thresholds(rules: list[ApprovalRule]) -> dict[tuple[str, str], int]:
    """Return the low-value approval ceiling for each country/category."""
    result: dict[tuple[str, str], int] = {}
    for rule in rules:
        if (
            rule.request_type == "expense"
            and rule.is_active
            and rule.max_amount_minor is not None
            and rule.category is not None
        ):
            key = (rule.country_code, rule.category)
            result[key] = max(result.get(key, 0), int(rule.max_amount_minor))
    return result


def matching_expense_rule_set(
    country_code: str,
    category: str,
    amount_minor: int,
    rules_by_country_category: dict[tuple[str, str], list[ApprovalRule]],
    expense_day: date,
) -> list[ApprovalRule]:
    candidates = rules_by_country_category.get((country_code, category), [])
    matching_by_set: dict[str, list[ApprovalRule]] = defaultdict(list)

    for rule in candidates:
        if not active_on_day(rule, "effective_start_date", "effective_end_date", expense_day):
            continue
        minimum = rule.min_amount_minor if rule.min_amount_minor is not None else 0
        maximum = rule.max_amount_minor
        if amount_minor >= minimum and (maximum is None or amount_minor <= maximum):
            matching_by_set[rule.rule_set_code].append(rule)

    if not matching_by_set:
        raise RuntimeError(
            f"No expense approval rule for {country_code}/{category}/{amount_minor}"
        )

    # There should be one matching rule set. Sorting makes the choice deterministic
    # if future policy configuration introduces overlapping ranges.
    matching_sets = sorted(
        matching_by_set.values(),
        key=lambda group: (
            max(
                (r.min_amount_minor or 0) for r in group
            ),
            group[0].rule_set_code,
        ),
        reverse=True,
    )
    selected = sorted(matching_sets[0], key=lambda rule: rule.step_order)
    return selected


def resolve_approver(
    requester: Employee,
    rule: ApprovalRule,
    employees_by_id: dict[str, Employee],
    employees_by_country: dict[str, list[Employee]],
) -> Employee:
    if rule.approver_type == "manager":
        manager = employees_by_id.get(requester.manager_employee_id)
        if (
            manager is not None
            and manager.employee_id != requester.employee_id
            and manager.country_code == requester.country_code
            and manager.employment_status == "active"
        ):
            return manager

        fallback = [
            employee
            for employee in employees_by_country.get(requester.country_code, [])
            if employee.employee_id != requester.employee_id
            and employee.system_role == "manager"
            and employee.employment_status == "active"
        ]
        if fallback:
            return sorted(fallback, key=lambda item: item.employee_id)[0]

        raise RuntimeError(f"No eligible manager approver for {requester.employee_id}")

    if rule.approver_type == "role":
        matches = [
            employee
            for employee in employees_by_country.get(requester.country_code, [])
            if employee.system_role == rule.approver_role
            and employee.employment_status == "active"
            and employee.employee_id != requester.employee_id
        ]
        if matches:
            return sorted(matches, key=lambda item: item.employee_id)[0]
        raise RuntimeError(
            f"No {rule.approver_role} approver in {requester.country_code}"
        )

    if rule.approver_type == "employee":
        approver = employees_by_id.get(rule.approver_employee_id)
        if (
            approver is not None
            and approver.employee_id != requester.employee_id
            and approver.country_code == requester.country_code
            and approver.employment_status == "active"
        ):
            return approver
        raise RuntimeError(f"Invalid employee approver in rule {rule.approval_rule_id}")

    raise RuntimeError(f"Unsupported approver_type={rule.approver_type}")


def choose_cost_center(
    employee: Employee,
    expense_day: date,
    assignments_by_employee: dict[str, list[EmployeeCostCenterAssignment]],
    cost_centers_by_id: dict[str, CostCenter],
) -> str | None:
    matches = []
    for assignment in assignments_by_employee.get(employee.employee_id, []):
        if not active_on_day(assignment, "effective_from", "effective_to", expense_day):
            continue
        center = cost_centers_by_id.get(assignment.cost_center_id)
        if (
            center is not None
            and center.is_active
            and center.country_code == employee.country_code
        ):
            matches.append((assignment, center))

    if not matches:
        return None

    matches.sort(
        key=lambda pair: (
            not pair[0].is_primary,
            pair[0].effective_from,
            pair[0].assignment_id,
        )
    )
    return matches[0][1].cost_center_id


def choose_status(rng: random.Random, force_review: bool, split_claim: bool = False) -> str:
    if force_review:
        return "needs_review"

    if split_claim:
        # A split claim must be submitted to be useful for retrospective detection.
        statuses = [
            "submitted",
            "pending_approval",
            "approved",
            "rejected",
            "cancelled",
        ]
        weights = [8, 20, 42, 12, 8]
        return rng.choices(statuses, weights=weights, k=1)[0]

    statuses = list(STATUS_WEIGHTS)
    weights = list(STATUS_WEIGHTS.values())
    return rng.choices(statuses, weights=weights, k=1)[0]


def make_normal_plan(
    rng: random.Random,
    employee: Employee,
    policy: ExpensePolicy,
    threshold: int,
    assignments_by_employee: dict[str, list[EmployeeCostCenterAssignment]],
    cost_centers_by_id: dict[str, CostCenter],
    forced_anomalies: set[str],
) -> dict:
    """Create a policy-compliant plan unless an explicit anomaly is requested."""
    per_item = int(policy.per_item_limit_minor)
    daily = int(policy.daily_limit_minor)
    claim_limit = int(policy.claim_limit_minor)
    per_line_cap = min(per_item, daily)

    if "policy_limit_breach" in forced_anomalies:
        # One line deliberately exceeds the configured per-item ceiling.
        line_amounts = [per_item + 1]
        line_count = 1
    else:
        max_normal_total = min(claim_limit, per_line_cap * 10)
        high_value = rng.random() < 0.42
        if high_value and max_normal_total > threshold:
            low_total = threshold + 1
            high_total = max_normal_total
        else:
            low_total = max(1, min(threshold, max(1, threshold // 4)))
            high_total = min(threshold, max_normal_total)

        if high_total < low_total:
            low_total = high_total
        total = rng.randint(max(1, low_total), max(1, high_total))
        line_count = max(rng.randint(1, 10), math.ceil(total / per_line_cap))
        line_count = min(10, line_count)
        total = min(total, line_count * per_line_cap)
        line_amounts = distribute_amount(total, line_count, per_line_cap, rng)

    earliest = max(START_DATE, employee.hire_date)
    if employee.termination_date is not None:
        latest_employment_day = employee.termination_date
    else:
        latest_employment_day = AS_OF_DATE
    available_days = max(1, (min(AS_OF_DATE, latest_employment_day) - earliest).days + 1)
    if line_count > available_days:
        # Keep every line on a distinct date so a normal claim cannot exceed
        # its daily limit merely because a recently hired employee has a short
        # employment window in the generated period.
        line_count = available_days
        total = min(sum(line_amounts), line_count * per_line_cap)
        total = max(line_count, total)
        line_amounts = distribute_amount(total, line_count, per_line_cap, rng)

    latest_possible_start = min(
        AS_OF_DATE - timedelta(days=line_count - 1),
        latest_employment_day - timedelta(days=line_count - 1),
    )
    if latest_possible_start < earliest:
        raise RuntimeError(f"No valid expense date window for {employee.employee_id}")

    span = max(0, (latest_possible_start - earliest).days)
    start_day = earliest + timedelta(days=rng.randint(0, span))
    line_dates = [start_day + timedelta(days=index) for index in range(line_count)]

    cost_center_id = choose_cost_center(
        employee,
        line_dates[0],
        assignments_by_employee,
        cost_centers_by_id,
    )
    if "missing_cost_center" in forced_anomalies:
        cost_center_id = None

    return {
        "employee": employee,
        "policy": policy,
        "line_amounts": line_amounts,
        "line_dates": line_dates,
        "cost_center_id": cost_center_id,
        "anomalies": set(forced_anomalies),
        "split_group_id": None,
    }


def make_out_of_employment_plan(
    rng: random.Random,
    employee: Employee,
    policy: ExpensePolicy,
    assignments_by_employee: dict[str, list[EmployeeCostCenterAssignment]],
    cost_centers_by_id: dict[str, CostCenter],
) -> dict:
    """Create a deliberately out-of-employment expense for review testing."""
    if employee.termination_date is not None:
        first_day = max(START_DATE, employee.termination_date + timedelta(days=1))
    elif employee.hire_date > START_DATE:
        first_day = employee.hire_date - timedelta(days=1)
    else:
        first_day = START_DATE

    if first_day > AS_OF_DATE:
        first_day = AS_OF_DATE

    available_days = max(1, (AS_OF_DATE - first_day).days + 1)
    line_count = min(rng.randint(1, 3), available_days)
    cap = min(int(policy.per_item_limit_minor), int(policy.daily_limit_minor))
    total = max(1, min(cap * line_count, int(policy.claim_limit_minor) // 3))
    line_amounts = distribute_amount(total, line_count, cap, rng)
    line_dates = [first_day + timedelta(days=index) for index in range(line_count)]

    cost_center_id = choose_cost_center(
        employee,
        line_dates[0],
        assignments_by_employee,
        cost_centers_by_id,
    )

    return {
        "employee": employee,
        "policy": policy,
        "line_amounts": line_amounts,
        "line_dates": line_dates,
        "cost_center_id": cost_center_id,
        "anomalies": {"out_of_employment_dates"},
        "split_group_id": None,
    }


def make_split_plan(
    employee: Employee,
    policy: ExpensePolicy,
    threshold: int,
    expense_day: date,
    cost_center_id: str | None,
    split_group_id: str,
) -> dict:
    amount = max(1, int(threshold * 0.60))
    amount = min(amount, int(policy.per_item_limit_minor), int(policy.daily_limit_minor))
    return {
        "employee": employee,
        "policy": policy,
        "line_amounts": [amount],
        "line_dates": [expense_day],
        "cost_center_id": cost_center_id,
        "anomalies": {"split_claim_candidate"},
        "split_group_id": split_group_id,
    }


def add_audit(
    audit_rows: list[AuditEvent],
    claim_number: int,
    sequence_by_claim: dict[int, int],
    entity_type: str,
    entity_id: str,
    event_type: str,
    actor_employee_id: str | None,
    occurred_at: datetime,
    before: dict | None = None,
    after: dict | None = None,
    details: dict | None = None,
) -> None:
    sequence_by_claim[claim_number] += 1
    event_id = f"AUD-EXP-2026-{claim_number:06d}-{sequence_by_claim[claim_number]:02d}"
    audit_rows.append(
        AuditEvent(
            audit_event_id=event_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            actor_employee_id=actor_employee_id,
            before_json=as_json(before) if before is not None else None,
            after_json=as_json(after) if after is not None else None,
            details_json=as_json(details) if details is not None else None,
            occurred_at=occurred_at,
        )
    )


def main() -> None:
    rng = random.Random(SEED)
    db = SessionLocal()

    try:
        # Refuse partial or duplicate generation. Leave workflow records are
        # intentionally ignored by these checks.
        existing_claims = db.query(ExpenseClaim).count()
        existing_lines = db.query(ExpenseLine).count()
        existing_reimbursements = db.query(Reimbursement).count()
        existing_expense_steps = (
            db.query(ApprovalStep)
            .filter(ApprovalStep.expense_claim_id.isnot(None))
            .count()
        )
        existing_expense_audits = (
            db.query(AuditEvent)
            .filter(
                (AuditEvent.entity_type == "expense_claim")
                | (AuditEvent.entity_type == "reimbursement")
                | (
                    (AuditEvent.entity_type == "approval_step")
                    & AuditEvent.entity_id.like("APR-EXP-2026-%")
                )
            )
            .count()
        )
        if any(
            [
                existing_claims,
                existing_lines,
                existing_reimbursements,
                existing_expense_steps,
                existing_expense_audits,
            ]
        ):
            raise RuntimeError(
                "Expense transaction data already exists. Generation stopped to protect it. "
                f"claims={existing_claims}, lines={existing_lines}, "
                f"reimbursements={existing_reimbursements}, approval_steps={existing_expense_steps}, "
                f"audit_events={existing_expense_audits}"
            )

        print("Loading master data...")
        employees = db.query(Employee).order_by(Employee.employee_id).all()
        policies = db.query(ExpensePolicy).filter(ExpensePolicy.is_active.is_(True)).order_by(
            ExpensePolicy.expense_policy_id
        ).all()
        cost_centers = db.query(CostCenter).filter(CostCenter.is_active.is_(True)).order_by(
            CostCenter.cost_center_id
        ).all()
        assignments = db.query(EmployeeCostCenterAssignment).order_by(
            EmployeeCostCenterAssignment.employee_id,
            EmployeeCostCenterAssignment.assignment_id,
        ).all()
        rules = db.query(ApprovalRule).filter(
            ApprovalRule.request_type == "expense",
            ApprovalRule.is_active.is_(True),
        ).order_by(ApprovalRule.approval_rule_id).all()

        if len(employees) < 50 or len(policies) != 12 or len(cost_centers) == 0:
            raise RuntimeError(
                f"Unexpected master data: employees={len(employees)}, "
                f"active_policies={len(policies)}, active_cost_centers={len(cost_centers)}"
            )

        employees_by_id = {employee.employee_id: employee for employee in employees}
        employees_by_country: dict[str, list[Employee]] = defaultdict(list)
        for employee in employees:
            employees_by_country[employee.country_code].append(employee)

        policies_by_country_category = {
            (policy.country_code, policy.category): policy for policy in policies
        }
        cost_centers_by_id = {center.cost_center_id: center for center in cost_centers}
        assignments_by_employee: dict[str, list[EmployeeCostCenterAssignment]] = defaultdict(list)
        for assignment in assignments:
            assignments_by_employee[assignment.employee_id].append(assignment)

        rules_by_country_category: dict[tuple[str, str], list[ApprovalRule]] = defaultdict(list)
        for rule in rules:
            if rule.category is not None:
                rules_by_country_category[(rule.country_code, rule.category)].append(rule)
        thresholds = build_policy_thresholds(rules)

        eligible_employees = [
            employee
            for employee in employees
            if employee.employment_status in {"active", "on_leave"}
            and employee.system_role in {"employee", "manager"}
            and employee.hire_date <= AS_OF_DATE
        ]
        terminated_employees = [
            employee
            for employee in employees
            if employee.employment_status == "terminated"
            and employee.system_role in {"employee", "manager"}
        ]
        if not eligible_employees:
            raise RuntimeError("No eligible employees found for expense generation")

        finance_admin_by_country = {}
        for country in sorted({employee.country_code for employee in employees}):
            admins = [
                employee
                for employee in employees_by_country[country]
                if employee.system_role == "finance_admin"
                and employee.employment_status == "active"
            ]
            if not admins:
                raise RuntimeError(f"Missing active finance_admin for country {country}")
            finance_admin_by_country[country] = sorted(admins, key=lambda item: item.employee_id)[0]

        print(f"Employees loaded: {len(employees)}")
        print(f"Expense policies loaded: {len(policies)}")
        print(f"Expense approval rules loaded: {len(rules)}")
        print(f"Cost centers loaded: {len(cost_centers)}")

        # Prepare 20 pairs (40 claims) whose individual values stay below the
        # approval threshold while their combined value crosses it.
        split_eligible_employees = [
            employee
            for employee in eligible_employees
            if any(
                assignment.effective_from <= AS_OF_DATE
                and (assignment.effective_to is None or assignment.effective_to >= START_DATE)
                and assignment.cost_center_id in cost_centers_by_id
                for assignment in assignments_by_employee.get(employee.employee_id, [])
            )
        ]
        split_employees = rng.sample(
            sorted(split_eligible_employees, key=lambda item: item.employee_id),
            k=min(20, len(split_eligible_employees)),
        )
        split_specs: dict[int, dict] = {}
        for pair_number, employee in enumerate(split_employees, start=1):
            policy = policies_by_country_category[(employee.country_code, "meals")]
            threshold = thresholds[(employee.country_code, "meals")]
            earliest = max(START_DATE, employee.hire_date)
            latest = AS_OF_DATE
            if employee.termination_date is not None:
                latest = min(latest, employee.termination_date)
            if earliest > latest:
                continue
            date_span = (latest - earliest).days
            expense_day = earliest + timedelta(days=rng.randint(0, date_span))
            cost_center_id = choose_cost_center(
                employee,
                expense_day,
                assignments_by_employee,
                cost_centers_by_id,
            )
            group_id = f"SPLIT-{pair_number:03d}"
            for claim_number in (pair_number * 2 - 1, pair_number * 2):
                split_specs[claim_number] = make_split_plan(
                    employee,
                    policy,
                    threshold,
                    expense_day,
                    cost_center_id,
                    group_id,
                )

        # Fixed, non-overlapping anomaly schedules make the dataset reproducible.
        missing_cost_center_indices = set(range(50, TARGET_CLAIMS + 1, 54))
        missing_receipt_indices = set(range(51, TARGET_CLAIMS + 1, 54))
        duplicate_receipt_indices = set(range(52, TARGET_CLAIMS + 1, 54))
        policy_breach_indices = set(range(53, TARGET_CLAIMS + 1, 54))
        out_of_employment_indices = set(range(991, 999))

        plans: list[dict] = []
        for claim_number in range(1, TARGET_CLAIMS + 1):
            if claim_number in split_specs:
                plans.append(split_specs[claim_number])
                continue

            anomalies: set[str] = set()
            if claim_number in missing_cost_center_indices:
                anomalies.add("missing_cost_center")
            if claim_number in missing_receipt_indices:
                anomalies.add("missing_receipt")
            if claim_number in duplicate_receipt_indices:
                anomalies.add("duplicate_receipt")
            if claim_number in policy_breach_indices:
                anomalies.add("policy_limit_breach")

            if claim_number in out_of_employment_indices and terminated_employees:
                employee = terminated_employees[(claim_number - 991) % len(terminated_employees)]
                policy = policies_by_country_category[
                    (employee.country_code, rng.choice(["travel", "meals", "accommodation", "office_supplies", "software", "training"]))
                ]
                plan = make_out_of_employment_plan(
                    rng,
                    employee,
                    policy,
                    assignments_by_employee,
                    cost_centers_by_id,
                )
                plans.append(plan)
                continue

            employee = rng.choice(eligible_employees)
            category = rng.choice(
                ["travel", "meals", "accommodation", "office_supplies", "software", "training"]
            )
            policy = policies_by_country_category[(employee.country_code, category)]
            threshold = thresholds[(employee.country_code, category)]
            plan = make_normal_plan(
                rng,
                employee,
                policy,
                threshold,
                assignments_by_employee,
                cost_centers_by_id,
                anomalies,
            )
            plans.append(plan)

        if len(plans) != TARGET_CLAIMS:
            raise RuntimeError(f"Prepared {len(plans)} plans, expected {TARGET_CLAIMS}")

        print(f"Prepared {len(plans)} expense claim plans.")
        print("Generating claims, line items, approvals, reimbursements and audit events...")

        claims_to_insert: list[ExpenseClaim] = []
        lines_to_insert: list[ExpenseLine] = []
        steps_to_insert: list[ApprovalStep] = []
        reimbursements_to_insert: list[Reimbursement] = []
        audit_rows: list[AuditEvent] = []
        claim_labels: list[dict] = []
        line_labels: list[dict] = []
        scenario_rows: list[dict] = []
        sequence_by_claim: dict[int, int] = defaultdict(int)
        known_receipt_hashes: list[str] = []
        approved_claim_context: list[dict] = []
        reimbursement_number = 0

        for claim_number, plan in enumerate(plans, start=1):
            claim_id = f"EXP-2026-{claim_number:06d}"
            employee: Employee = plan["employee"]
            policy: ExpensePolicy = plan["policy"]
            anomalies: set[str] = set(plan["anomalies"])
            line_amounts: list[int] = plan["line_amounts"]
            line_dates: list[date] = plan["line_dates"]
            total_amount = sum(line_amounts)
            first_day = min(line_dates)
            last_day = max(line_dates)
            cost_center_id = plan["cost_center_id"]

            # If no valid assignment exists, explicitly label the missing cost center.
            if cost_center_id is None:
                anomalies.add("missing_cost_center")

            force_review = bool(
                anomalies
                & {
                    "missing_cost_center",
                    "missing_receipt",
                    "duplicate_receipt",
                    "policy_limit_breach",
                    "out_of_employment_dates",
                }
            )
            is_split = "split_claim_candidate" in anomalies
            status = choose_status(rng, force_review, is_split)

            created_at = random_datetime(rng, last_day)
            if status == "draft":
                submitted_at = None
            else:
                submitted_at = clamp_datetime(
                    created_at + timedelta(hours=rng.randint(1, 48))
                )
            if submitted_at is not None and submitted_at < created_at:
                submitted_at = created_at

            final_decision_at = None
            if status in {"approved", "rejected", "cancelled"}:
                final_decision_at = clamp_datetime(
                    submitted_at + timedelta(hours=rng.randint(2, 96))
                )

            purpose = BUSINESS_PURPOSES[policy.category]
            if is_split:
                purpose = f"Client meeting refreshments - {plan['split_group_id']}"

            claim = ExpenseClaim(
                expense_claim_id=claim_id,
                employee_id=employee.employee_id,
                cost_center_id=cost_center_id,
                country_code=employee.country_code,
                currency_code=policy.currency_code,
                business_purpose=purpose,
                expense_start_date=first_day,
                expense_end_date=last_day,
                primary_category=policy.category,
                total_amount_minor=total_amount,
                status=status,
                submitted_at=submitted_at,
                final_decision_at=final_decision_at,
                created_at=created_at,
            )
            claims_to_insert.append(claim)

            claim_line_anomalies: set[str] = set()
            for line_number, (amount, expense_day) in enumerate(
                zip(line_amounts, line_dates), start=1
            ):
                line_id = f"EXPL-{claim_id}-{line_number:02d}"
                has_receipt = not (
                    "missing_receipt" in anomalies and line_number == 1
                )
                receipt_hash = None
                receipt_filename = None
                receipt_mime_type = None
                receipt_uploaded_at = None

                if has_receipt:
                    if "duplicate_receipt" in anomalies and line_number == 1 and known_receipt_hashes:
                        receipt_hash = rng.choice(known_receipt_hashes)
                        claim_line_anomalies.add("duplicate_receipt")
                    else:
                        receipt_hash = hashlib.sha256(
                            f"EmployeeFlow|{claim_id}|{line_number}|{amount}".encode("utf-8")
                        ).hexdigest()
                        known_receipt_hashes.append(receipt_hash)
                    extension, mime = rng.choice(
                        [("pdf", "application/pdf"), ("jpg", "image/jpeg"), ("png", "image/png")]
                    )
                    receipt_filename = f"{claim_id}_{line_number:02d}.{extension}"
                    receipt_mime_type = mime
                    receipt_uploaded_at = datetime.combine(expense_day, time(18, 0))
                else:
                    claim_line_anomalies.add("missing_receipt")

                if amount > int(policy.per_item_limit_minor):
                    claim_line_anomalies.add("per_item_limit_breach")

                line = ExpenseLine(
                    expense_line_id=line_id,
                    expense_claim_id=claim_id,
                    expense_policy_id=policy.expense_policy_id,
                    line_number=line_number,
                    expense_date=expense_day,
                    category=policy.category,
                    description=DESCRIPTIONS[policy.category],
                    merchant=rng.choice(MERCHANTS[policy.category]),
                    amount_minor=amount,
                    receipt_filename=receipt_filename,
                    receipt_sha256=receipt_hash,
                    receipt_mime_type=receipt_mime_type,
                    receipt_uploaded_at=receipt_uploaded_at,
                )
                lines_to_insert.append(line)

                line_labels.append(
                    {
                        "expense_line_id": line_id,
                        "expense_claim_id": claim_id,
                        "line_number": line_number,
                        "amount_minor": amount,
                        "category": policy.category,
                        "missing_receipt": not has_receipt,
                        "duplicate_receipt": (
                            "duplicate_receipt" in anomalies
                            and line_number == 1
                            and has_receipt
                        ),
                        "per_item_limit_breach": amount > int(policy.per_item_limit_minor),
                    }
                )

            if "policy_limit_breach" in anomalies:
                claim_line_anomalies.add("policy_limit_breach")
            if total_amount > int(policy.claim_limit_minor):
                claim_line_anomalies.add("claim_limit_breach")
            anomalies.update(claim_line_anomalies)

            # Resolve the approval path from the actual ApprovalRule records.
            matched_rules = matching_expense_rule_set(
                employee.country_code,
                policy.category,
                total_amount,
                rules_by_country_category,
                first_day,
            )
            rule_set_code = matched_rules[0].rule_set_code if matched_rules else ""

            add_audit(
                audit_rows,
                claim_number,
                sequence_by_claim,
                "expense_claim",
                claim_id,
                "expense_claim_created",
                employee.employee_id,
                created_at,
                after={
                    "status": status,
                    "total_amount_minor": total_amount,
                    "currency_code": policy.currency_code,
                    "category": policy.category,
                },
                details={"seed": SEED, "generator": "generate_expense_transactions.py"},
            )

            if submitted_at is not None:
                add_audit(
                    audit_rows,
                    claim_number,
                    sequence_by_claim,
                    "expense_claim",
                    claim_id,
                    "expense_claim_submitted",
                    employee.employee_id,
                    submitted_at,
                    before={"status": "draft"},
                    after={"status": status},
                )

            if status == "needs_review":
                add_audit(
                    audit_rows,
                    claim_number,
                    sequence_by_claim,
                    "expense_claim",
                    claim_id,
                    "expense_claim_flagged_for_review",
                    None,
                    submitted_at or created_at,
                    after={"status": "needs_review"},
                    details={"edge_cases": sorted(anomalies)},
                )

            claim_steps: list[ApprovalStep] = []
            if status in {"pending_approval", "approved", "rejected", "cancelled"}:
                approvers = [
                    resolve_approver(
                        employee,
                        rule,
                        employees_by_id,
                        employees_by_country,
                    )
                    for rule in matched_rules
                ]
                if any(approver.employee_id == employee.employee_id for approver in approvers):
                    raise RuntimeError(f"Self-approval detected for {claim_id}")

                rejected_index = rng.randrange(len(matched_rules)) if status == "rejected" else None
                for step_index, (rule, approver) in enumerate(zip(matched_rules, approvers)):
                    if status == "approved":
                        step_status = "approved"
                        decided_at = final_decision_at
                        reason = "Approved according to configured expense approval policy"
                    elif status == "pending_approval":
                        step_status = "pending"
                        decided_at = None
                        reason = None
                    elif status == "cancelled":
                        step_status = "skipped"
                        decided_at = final_decision_at
                        reason = "Request cancelled before approval was completed"
                    else:
                        if step_index < rejected_index:
                            step_status = "approved"
                            reason = "Approved; forwarded to the next approval level"
                        elif step_index == rejected_index:
                            step_status = "rejected"
                            reason = "Rejected after policy and business review"
                        else:
                            step_status = "skipped"
                            reason = "Skipped because an earlier approval step rejected the claim"
                        decided_at = final_decision_at

                    step_id = f"APR-{claim_id}-{rule.step_order:02d}"
                    step = ApprovalStep(
                        approval_step_id=step_id,
                        leave_request_id=None,
                        expense_claim_id=claim_id,
                        approval_rule_id=rule.approval_rule_id,
                        approver_employee_id=approver.employee_id,
                        step_order=rule.step_order,
                        status=step_status,
                        decision_reason=reason,
                        assigned_at=submitted_at,
                        decided_at=decided_at,
                    )
                    claim_steps.append(step)
                    steps_to_insert.append(step)

                    add_audit(
                        audit_rows,
                        claim_number,
                        sequence_by_claim,
                        "approval_step",
                        step_id,
                        "approval_step_assigned",
                        employee.employee_id,
                        submitted_at,
                        after={
                            "approver_employee_id": approver.employee_id,
                            "approval_rule_id": rule.approval_rule_id,
                            "step_order": rule.step_order,
                            "status": step_status,
                        },
                    )
                    if step_status in {"approved", "rejected", "skipped"}:
                        add_audit(
                            audit_rows,
                            claim_number,
                            sequence_by_claim,
                            "approval_step",
                            step_id,
                            f"approval_step_{step_status}",
                            approver.employee_id,
                            decided_at or submitted_at,
                            before={"status": "pending"},
                            after={"status": step_status},
                            details={"decision_reason": reason},
                        )

            if status in {"approved", "rejected", "cancelled"}:
                add_audit(
                    audit_rows,
                    claim_number,
                    sequence_by_claim,
                    "expense_claim",
                    claim_id,
                    f"expense_claim_{status}",
                    None,
                    final_decision_at,
                    before={"status": "pending_approval"},
                    after={"status": status},
                    details={"approval_rule_set": rule_set_code},
                )

            if status == "approved":
                reimbursement_number += 1
                reimbursement_id = f"RMB-2026-{reimbursement_number:06d}"
                reimbursement_status = rng.choices(
                    list(REIMBURSEMENT_STATUS_WEIGHTS),
                    weights=list(REIMBURSEMENT_STATUS_WEIGHTS.values()),
                    k=1,
                )[0]
                reimbursement_created_at = final_decision_at
                paid_at = None
                if reimbursement_status == "paid":
                    paid_at = clamp_datetime(
                        reimbursement_created_at + timedelta(hours=rng.randint(1, 72))
                    )
                payment_reference = None
                if reimbursement_status in {"paid", "failed"}:
                    payment_reference = f"PAY-2026-{reimbursement_number:06d}"

                finance_admin = finance_admin_by_country[employee.country_code]
                reimbursement = Reimbursement(
                    reimbursement_id=reimbursement_id,
                    expense_claim_id=claim_id,
                    amount_minor=total_amount,
                    currency_code=policy.currency_code,
                    status=reimbursement_status,
                    payment_reference=payment_reference,
                    created_by_employee_id=finance_admin.employee_id,
                    paid_at=paid_at,
                    created_at=reimbursement_created_at,
                )
                reimbursements_to_insert.append(reimbursement)

                add_audit(
                    audit_rows,
                    claim_number,
                    sequence_by_claim,
                    "reimbursement",
                    reimbursement_id,
                    "reimbursement_created",
                    finance_admin.employee_id,
                    reimbursement_created_at,
                    after={
                        "amount_minor": total_amount,
                        "currency_code": policy.currency_code,
                        "status": reimbursement_status,
                    },
                )
                if reimbursement_status == "paid":
                    add_audit(
                        audit_rows,
                        claim_number,
                        sequence_by_claim,
                        "reimbursement",
                        reimbursement_id,
                        "reimbursement_paid",
                        finance_admin.employee_id,
                        paid_at,
                        before={"status": "pending_payment"},
                        after={"status": "paid", "payment_reference": payment_reference},
                    )

                approved_claim_context.append(
                    {
                        "claim_id": claim_id,
                        "employee_id": employee.employee_id,
                        "approver_ids": [step.approver_employee_id for step in claim_steps],
                        "reimbursement_id": reimbursement_id,
                    }
                )

            expected_outcome = "normal_processing"
            if anomalies:
                expected_outcome = "flag_or_investigate"
            if "out_of_employment_dates" in anomalies:
                expected_outcome = "block_or_manual_review"
            if "split_claim_candidate" in anomalies:
                expected_outcome = "detect_related_claims_for_threshold_review"

            claim_labels.append(
                {
                    "expense_claim_id": claim_id,
                    "employee_id": employee.employee_id,
                    "country_code": employee.country_code,
                    "currency_code": policy.currency_code,
                    "category": policy.category,
                    "line_count": len(line_amounts),
                    "total_amount_minor": total_amount,
                    "status": status,
                    "approval_rule_set": rule_set_code,
                    "approval_step_count": len(claim_steps),
                    "reimbursement_id": (
                        reimbursements_to_insert[-1].reimbursement_id
                        if status == "approved"
                        else ""
                    ),
                    "reimbursement_status": (
                        reimbursements_to_insert[-1].status
                        if status == "approved"
                        else ""
                    ),
                    "split_group_id": plan.get("split_group_id") or "",
                    "edge_case_type": ";".join(sorted(anomalies)),
                    "expected_outcome": expected_outcome,
                }
            )

        # Scenarios document rejected actions without persisting invalid records.
        # This preserves the no-self-approval rule and reimbursement uniqueness.
        for index, context in enumerate(approved_claim_context[:10], start=1):
            scenario_rows.append(
                {
                    "scenario_id": f"SCN-SELF-{index:04d}",
                    "expense_claim_id": context["claim_id"],
                    "scenario_type": "self_approval_attempt",
                    "requester_employee_id": context["employee_id"],
                    "proposed_approver_employee_id": context["employee_id"],
                    "expected_outcome": "blocked_self_approval",
                    "expected_reason": "An employee cannot approve their own expense claim",
                }
            )
            scenario_rows.append(
                {
                    "scenario_id": f"SCN-DUP-RMB-{index:04d}",
                    "expense_claim_id": context["claim_id"],
                    "scenario_type": "duplicate_reimbursement_attempt",
                    "requester_employee_id": context["employee_id"],
                    "proposed_approver_employee_id": "",
                    "expected_outcome": "blocked_unique_constraint",
                    "expected_reason": "Only one reimbursement is allowed per expense claim",
                }
            )

        print("Writing records to the database...")
        db.add_all(claims_to_insert)
        db.flush()
        db.add_all(lines_to_insert)
        db.flush()
        db.add_all(steps_to_insert)
        db.flush()
        db.add_all(reimbursements_to_insert)
        db.flush()
        db.add_all(audit_rows)
        db.commit()

        project_root = Path(__file__).resolve().parents[1]
        ground_truth_dir = project_root / "data" / "ground_truth"

        write_csv(
            ground_truth_dir / "expense_claim_labels.csv",
            claim_labels,
            [
                "expense_claim_id",
                "employee_id",
                "country_code",
                "currency_code",
                "category",
                "line_count",
                "total_amount_minor",
                "status",
                "approval_rule_set",
                "approval_step_count",
                "reimbursement_id",
                "reimbursement_status",
                "split_group_id",
                "edge_case_type",
                "expected_outcome",
            ],
        )
        write_csv(
            ground_truth_dir / "expense_line_labels.csv",
            line_labels,
            [
                "expense_line_id",
                "expense_claim_id",
                "line_number",
                "amount_minor",
                "category",
                "missing_receipt",
                "duplicate_receipt",
                "per_item_limit_breach",
            ],
        )
        write_csv(
            ground_truth_dir / "expense_control_test_scenarios.csv",
            scenario_rows,
            [
                "scenario_id",
                "expense_claim_id",
                "scenario_type",
                "requester_employee_id",
                "proposed_approver_employee_id",
                "expected_outcome",
                "expected_reason",
            ],
        )

        status_counts = Counter(row["status"] for row in claim_labels)
        edge_counts = Counter()
        for row in claim_labels:
            for edge in filter(None, row["edge_case_type"].split(";")):
                edge_counts[edge] += 1

        print("\n" + "=" * 58)
        print("EXPENSE TRANSACTION GENERATION SUCCESSFUL")
        print("=" * 58)
        print(f"Expense claims: {len(claims_to_insert)}")
        print(f"Expense lines: {len(lines_to_insert)}")
        print(f"Approval steps: {len(steps_to_insert)}")
        print(f"Reimbursements: {len(reimbursements_to_insert)}")
        print(f"Audit events: {len(audit_rows)}")
        print("\nClaim status distribution:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        print("\nGround-truth edge-case counts:")
        for edge, count in sorted(edge_counts.items()):
            print(f"  {edge}: {count}")
        print("\nGround-truth files:")
        print(ground_truth_dir / "expense_claim_labels.csv")
        print(ground_truth_dir / "expense_line_labels.csv")
        print(ground_truth_dir / "expense_control_test_scenarios.csv")
        print("\nExpense transaction generation completed!")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
