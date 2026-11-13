
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

from app.db.session import SessionLocal
from app.models import (
    Employee,
    LeavePolicy,
    LeaveBalance,
    LeaveRequest,
    EmployeeLeavePolicyAssignment,
    Holiday,
    ApprovalRule,
    ApprovalStep,
    AuditEvent,
)


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

SEED = 20261022
YEAR = 2026
TARGET_REQUESTS = 800

START_OF_YEAR = date(2026, 1, 1)
END_OF_YEAR = date(2026, 12, 31)
AS_OF_DATE = date(2026, 11, 11)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_DIR = PROJECT_ROOT / "data" / "ground_truth"

rng = random.Random(SEED)

REASONS = [
    "Family commitments",
    "Personal work",
    "Medical appointment",
    "Family function",
    "Vacation",
    "Personal reasons",
    "Rest and recovery",
    "Travel plans",
    "Family emergency",
    "Annual leave",
]

STATUS_OPTIONS = [
    "draft",
    "submitted",
    "pending_approval",
    "needs_review",
    "approved",
    "rejected",
    "cancelled",
]

STATUS_WEIGHTS = [5, 8, 20, 5, 42, 12, 8]


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def decimal_value(value):
    return Decimal(str(value or 0))


def round_days(value):
    return Decimal(value).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def make_datetime(day):
    """
    Generate deterministic naive UTC timestamps.
    """

    return datetime.combine(
        day,
        time(
            hour=rng.randint(9, 15),
            minute=rng.choice([0, 15, 30, 45]),
        ),
    )


def is_business_day(day, holidays):
    return day.weekday() < 5 and day not in holidays


def next_business_day(day, holidays):
    while not is_business_day(day, holidays):
        day += timedelta(days=1)

    return day


def calculate_business_days(start_date, end_date, holidays):
    total = 0
    current = start_date

    while current <= end_date:
        if is_business_day(current, holidays):
            total += 1

        current += timedelta(days=1)

    return total


def calculate_end_date(start_date, requested_days, holidays):
    """
    Calculate an end date for a requested number
    of business days.
    """

    current = start_date
    count = 0

    while count < requested_days:
        if is_business_day(current, holidays):
            count += 1

        if count < requested_days:
            current += timedelta(days=1)

    return current


def choose_request_dates(
    employee,
    assignment,
    policy,
    requested_days,
    holidays,
):
    """
    Select valid leave dates within employment,
    policy and assignment effective dates.
    """

    min_notice = max(0, int(policy.min_notice_days))

    earliest_submit = max(
        START_OF_YEAR,
        employee.hire_date,
    )

    min_start = max(
        START_OF_YEAR,
        employee.hire_date,
        assignment.effective_from,
        policy.effective_start_date,
    )

    max_start = min(
        END_OF_YEAR,
        assignment.effective_to or END_OF_YEAR,
        employee.termination_date or END_OF_YEAR,
        policy.effective_end_date or END_OF_YEAR,
    )

    if min_start > max_start:
        return None

    earliest_start = max(
        min_start,
        earliest_submit + timedelta(days=min_notice + 1),
    )

    latest_submit_limit = AS_OF_DATE - timedelta(days=10)

    possible_starts = []

    current = earliest_start

    while current <= max_start:

        if is_business_day(current, holidays):

            latest_submit = min(
                latest_submit_limit,
                current - timedelta(days=min_notice + 1),
            )

            if latest_submit >= earliest_submit:
                possible_starts.append((current, latest_submit))

        current += timedelta(days=1)

    if not possible_starts:
        return None

    start_date, latest_submit = rng.choice(possible_starts)

    submit_range = (latest_submit - earliest_submit).days

    submitted_date = earliest_submit + timedelta(
        days=rng.randint(0, submit_range)
    )

    actual_days = requested_days

    end_date = calculate_end_date(
        start_date,
        actual_days,
        holidays,
    )

    # Keep the request within employment and policy dates.
    while end_date > max_start and actual_days > 1:
        actual_days -= 1

        end_date = calculate_end_date(
            start_date,
            actual_days,
            holidays,
        )

    if end_date > max_start:
        return None

    return start_date, end_date, submitted_date, actual_days


# --------------------------------------------------
# APPROVAL RULE SELECTION
# --------------------------------------------------

def get_leave_approval_rules(
    approval_rules,
    country_code,
    business_days,
    request_date,
):
    matching = []

    for rule in approval_rules:

        if rule.request_type != "leave":
            continue

        if rule.country_code != country_code:
            continue

        if not rule.is_active:
            continue

        if rule.effective_start_date > request_date:
            continue

        if (
            rule.effective_end_date is not None
            and rule.effective_end_date < request_date
        ):
            continue

        if (
            rule.min_leave_days is not None
            and business_days < rule.min_leave_days
        ):
            continue

        if (
            rule.max_leave_days is not None
            and business_days > rule.max_leave_days
        ):
            continue

        matching.append(rule)

    if not matching:
        return []

    # Group rules into approval rule sets.
    groups = defaultdict(list)

    for rule in matching:
        groups[rule.rule_set_code].append(rule)

    # Prefer the highest-priority matching rule set.
    selected_group = sorted(
        groups.values(),
        key=lambda group: (
            min(rule.priority for rule in group),
            -len(group),
            group[0].rule_set_code,
        ),
    )[0]

    return sorted(
        selected_group,
        key=lambda rule: rule.step_order,
    )


# --------------------------------------------------
# APPROVER RESOLUTION
# --------------------------------------------------

def resolve_approver(rule, requester, employees):

    approver = None

    if rule.approver_type == "manager":

        manager = employees.get(requester.manager_employee_id)

        if (
            manager is not None
            and manager.employee_id != requester.employee_id
            and manager.country_code == requester.country_code
            and manager.employment_status == "active"
        ):
            approver = manager

        else:
            # Managers without managers are routed
            # to another manager in their country.
            candidates = [
                employee
                for employee in employees.values()
                if employee.country_code == requester.country_code
                and employee.system_role == "manager"
                and employee.employment_status == "active"
                and employee.employee_id != requester.employee_id
            ]

            if candidates:
                approver = sorted(
                    candidates,
                    key=lambda employee: employee.employee_id,
                )[0]

    elif rule.approver_type == "role":

        candidates = [
            employee
            for employee in employees.values()
            if employee.country_code == requester.country_code
            and employee.system_role == rule.approver_role
            and employee.employment_status == "active"
            and employee.employee_id != requester.employee_id
        ]

        if candidates:
            approver = sorted(
                candidates,
                key=lambda employee: employee.employee_id,
            )[0]

    elif rule.approver_type == "employee":

        approver = employees.get(rule.approver_employee_id)

        if approver and approver.employee_id == requester.employee_id:
            approver = None

    if approver is None:
        raise ValueError(
            f"No valid approver found for "
            f"{requester.employee_id}, rule {rule.approval_rule_id}"
        )

    return approver


# --------------------------------------------------
# AUDIT EVENT CREATION
# --------------------------------------------------

def add_audit_event(
    session,
    request_number,
    sequence,
    entity_type,
    entity_id,
    event_type,
    actor_employee_id,
    occurred_at,
    before=None,
    after=None,
    details=None,
):

    event = AuditEvent(
        audit_event_id=(
            f"AUD-LVE-2026-{request_number:06d}-{sequence:02d}"
        ),
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        actor_employee_id=actor_employee_id,
        before_json=json.dumps(before, default=str) if before else None,
        after_json=json.dumps(after, default=str) if after else None,
        details_json=json.dumps(details, default=str) if details else None,
        occurred_at=occurred_at,
    )

    session.add(event)

    return sequence + 1


# --------------------------------------------------
# MAIN GENERATOR
# --------------------------------------------------

def generate_leave_transactions():

    session = SessionLocal()

    try:

        # Prevent duplicate transaction generation.
        existing = session.query(LeaveRequest).count()

        if existing > 0:
            print(
                f"Leave requests already exist ({existing}). "
                "Skipping generation."
            )
            return

        print("Loading master data...")

        employees = {
            employee.employee_id: employee
            for employee in session.query(Employee).all()
        }

        policies = {
            policy.leave_policy_id: policy
            for policy in session.query(LeavePolicy).all()
        }

        balances = {
            (balance.employee_id, balance.leave_policy_id): balance
            for balance in session.query(LeaveBalance)
            .filter(LeaveBalance.period_year == YEAR)
            .all()
        }

        approval_rules = session.query(ApprovalRule).all()

        holiday_map = defaultdict(set)

        for holiday in session.query(Holiday).all():
            holiday_map[holiday.country_code].add(
                holiday.holiday_date
            )

        assignments = (
            session.query(EmployeeLeavePolicyAssignment)
            .filter(
                EmployeeLeavePolicyAssignment.is_active.is_(True)
            )
            .all()
        )

        # --------------------------------------------------
        # BUILD ELIGIBLE EMPLOYEE-POLICY COMBINATIONS
        # --------------------------------------------------

        candidates = []
        seen_pairs = set()

        for assignment in assignments:

            employee = employees.get(assignment.employee_id)
            policy = policies.get(assignment.leave_policy_id)

            if employee is None or policy is None:
                continue

            balance = balances.get(
                (employee.employee_id, policy.leave_policy_id)
            )

            if balance is None:
                continue

            if employee.employment_status not in ("active", "on_leave"):
                continue

            # Exclude administrators to avoid self-approval
            # and preserve one approver per country and role.
            if employee.system_role not in ("employee", "manager"):
                continue

            if employee.country_code != policy.country_code:
                continue

            if not policy.is_active:
                continue

            pair = (
                employee.employee_id,
                policy.leave_policy_id,
            )

            if pair in seen_pairs:
                continue

            seen_pairs.add(pair)

            candidates.append(
                (assignment, employee, policy, balance)
            )

        candidates.sort(
            key=lambda item: (
                item[1].employee_id,
                item[2].leave_policy_id,
            )
        )

        rng.shuffle(candidates)

        # --------------------------------------------------
        # PREPARE 800 VALID REQUEST PLANS
        # --------------------------------------------------

        plans = []

        for assignment, employee, policy, balance in candidates:

            available_before = decimal_value(
                balance.available_days
            )

            policy_limit = policy.max_consecutive_days or 10
            policy_limit = max(1, min(10, int(policy_limit)))

            available_floor = max(
                0,
                int(
                    available_before.to_integral_value(
                        rounding=ROUND_FLOOR
                    )
                ),
            )

            if available_floor >= 1:
                max_days = min(policy_limit, available_floor)
            else:
                max_days = 1

            requested_days = rng.randint(1, max_days)

            dates = choose_request_dates(
                employee,
                assignment,
                policy,
                requested_days,
                holiday_map[employee.country_code],
            )

            if dates is None:
                continue

            start_date, end_date, submitted_date, actual_days = dates

            plans.append({
                "assignment": assignment,
                "employee": employee,
                "policy": policy,
                "balance": balance,
                "available_before": available_before,
                "start_date": start_date,
                "end_date": end_date,
                "submitted_date": submitted_date,
                "business_days": actual_days,
            })

            if len(plans) == TARGET_REQUESTS:
                break

        if len(plans) < TARGET_REQUESTS:
            raise ValueError(
                f"Only {len(plans)} valid leave plans could be created. "
                f"Required: {TARGET_REQUESTS}."
            )

        print(f"Prepared {len(plans)} leave request plans.")
        print("Generating requests, approvals and audit events...")

        # --------------------------------------------------
        # CREATE TRANSACTIONAL RECORDS
        # --------------------------------------------------

        status_counter = Counter()
        total_steps = 0
        total_audits = 0
        labels = []

        for number, plan in enumerate(plans, start=1):

            employee = plan["employee"]
            policy = plan["policy"]
            balance = plan["balance"]

            start_date = plan["start_date"]
            end_date = plan["end_date"]
            submitted_date = plan["submitted_date"]

            business_days = plan["business_days"]
            requested_amount = Decimal(business_days)

            available_before = plan["available_before"]

            insufficient_balance = (
                available_before < requested_amount
            )

            status = rng.choices(
                STATUS_OPTIONS,
                weights=STATUS_WEIGHTS,
                k=1,
            )[0]

            # Insufficient balance requires manual review.
            if insufficient_balance:
                status = "needs_review"

            elif (
                not policy.requires_approval
                and status in (
                    "submitted",
                    "pending_approval",
                    "needs_review",
                    "rejected",
                )
            ):
                status = "approved"

            holidays = holiday_map[employee.country_code]

            calculated_days = calculate_business_days(
                start_date,
                end_date,
                holidays,
            )

            if calculated_days != business_days:
                raise ValueError(
                    f"Business-day mismatch for request {number}"
                )

            rules = get_leave_approval_rules(
                approval_rules,
                employee.country_code,
                business_days,
                start_date,
            ) if policy.requires_approval else []

            if policy.requires_approval and not rules:
                raise ValueError(
                    f"No matching approval rule for "
                    f"{employee.country_code}, {business_days} days"
                )

            request_id = f"LVE-2026-{number:06d}"

            created_at = make_datetime(submitted_date)

            submitted_at = None

            if status != "draft":
                submitted_at = created_at + timedelta(
                    minutes=rng.randint(5, 45)
                )

            final_decision_at = None
            rejected_index = None

            if status in ("approved", "rejected", "cancelled"):

                if status == "approved":
                    decision_days = max(1, len(rules))

                elif status == "rejected":
                    rejected_index = (
                        rng.randrange(len(rules))
                        if rules else 0
                    )
                    decision_days = rejected_index + 1

                else:
                    decision_days = 1

                final_decision_at = make_datetime(
                    submitted_date + timedelta(days=decision_days)
                )

            request = LeaveRequest(
                leave_request_id=request_id,
                employee_id=employee.employee_id,
                leave_policy_id=policy.leave_policy_id,
                start_date=start_date,
                end_date=end_date,
                business_days=round_days(business_days),
                reason=rng.choice(REASONS),
                status=status,
                submitted_at=submitted_at,
                final_decision_at=final_decision_at,
                created_at=created_at,
            )

            session.add(request)
            session.flush()

            status_counter[status] += 1

            # --------------------------------------------------
            # AUDIT: REQUEST CREATED
            # --------------------------------------------------

            audit_sequence = 1

            audit_sequence = add_audit_event(
                session,
                number,
                audit_sequence,
                "leave_request",
                request_id,
                "leave_request.created",
                employee.employee_id,
                created_at,
                after={
                    "status": status,
                    "business_days": business_days,
                    "leave_policy_id": policy.leave_policy_id,
                },
            )

            if submitted_at is not None:

                audit_sequence = add_audit_event(
                    session,
                    number,
                    audit_sequence,
                    "leave_request",
                    request_id,
                    "leave_request.submitted",
                    employee.employee_id,
                    submitted_at,
                    after={"status": status},
                )

            # --------------------------------------------------
            # CREATE APPROVAL STEPS
            # --------------------------------------------------

            final_actor = employee.employee_id

            create_steps = (
                status in (
                    "pending_approval",
                    "approved",
                    "rejected",
                    "cancelled",
                )
                and bool(rules)
            )

            if create_steps:

                for index, rule in enumerate(rules):

                    approver = resolve_approver(
                        rule,
                        employee,
                        employees,
                    )

                    assigned_at = submitted_at + timedelta(
                        minutes=5 * rule.step_order
                    )

                    step_status = "pending"
                    decided_at = None
                    decision_reason = None

                    if status == "approved":

                        step_status = "approved"

                        decided_at = make_datetime(
                            submitted_date
                            + timedelta(days=rule.step_order)
                        )

                        decision_reason = (
                            "Approved under the applicable leave rule."
                        )

                    elif status == "rejected":

                        if index < rejected_index:
                            step_status = "approved"

                            decided_at = make_datetime(
                                submitted_date
                                + timedelta(days=index + 1)
                            )

                            decision_reason = (
                                "Approved before the subsequent rejection."
                            )

                        elif index == rejected_index:
                            step_status = "rejected"
                            decided_at = final_decision_at

                            decision_reason = (
                                "Rejected during simulated approval review."
                            )

                            final_actor = approver.employee_id

                        else:
                            step_status = "skipped"
                            decided_at = final_decision_at

                            decision_reason = (
                                "Skipped because an earlier step rejected "
                                "the request."
                            )

                    elif status == "cancelled":

                        step_status = "skipped"
                        decided_at = final_decision_at

                        decision_reason = (
                            "Skipped because the request was cancelled."
                        )

                    elif status == "pending_approval":

                        decision_reason = (
                            "Awaiting approver decision."
                        )

                    step_id = (
                        f"APR-{request_id}-{rule.step_order:02d}"
                    )

                    step = ApprovalStep(
                        approval_step_id=step_id,
                        leave_request_id=request_id,
                        expense_claim_id=None,
                        approval_rule_id=rule.approval_rule_id,
                        approver_employee_id=approver.employee_id,
                        step_order=rule.step_order,
                        status=step_status,
                        decision_reason=decision_reason,
                        assigned_at=assigned_at,
                        decided_at=decided_at,
                    )

                    session.add(step)
                    session.flush()

                    total_steps += 1

                    audit_sequence = add_audit_event(
                        session,
                        number,
                        audit_sequence,
                        "approval_step",
                        step_id,
                        "approval_step.assigned",
                        None,
                        assigned_at,
                        after={
                            "approver_employee_id": approver.employee_id,
                            "status": step_status,
                            "approval_rule_id": rule.approval_rule_id,
                        },
                    )

                    if decided_at is not None:

                        audit_sequence = add_audit_event(
                            session,
                            number,
                            audit_sequence,
                            "approval_step",
                            step_id,
                            f"approval_step.{step_status}",
                            approver.employee_id,
                            decided_at,
                            after={
                                "status": step_status,
                                "decision_reason": decision_reason,
                            },
                        )

            # --------------------------------------------------
            # AUDIT: FINAL REQUEST STATUS
            # --------------------------------------------------

            if status in (
                "approved",
                "rejected",
                "cancelled",
            ):

                audit_sequence = add_audit_event(
                    session,
                    number,
                    audit_sequence,
                    "leave_request",
                    request_id,
                    f"leave_request.{status}",
                    final_actor,
                    final_decision_at,
                    after={"status": status},
                )

            elif status == "needs_review":

                audit_sequence = add_audit_event(
                    session,
                    number,
                    audit_sequence,
                    "leave_request",
                    request_id,
                    "leave_request.needs_review",
                    None,
                    submitted_at,
                    after={"status": status},
                    details={
                        "insufficient_balance": insufficient_balance,
                    },
                )

            # --------------------------------------------------
            # UPDATE LEAVE BALANCE
            # --------------------------------------------------

            if status == "approved":

                balance.approved_used_days = round_days(
                    decimal_value(balance.approved_used_days)
                    + requested_amount
                )

            elif (
                status in (
                    "submitted",
                    "pending_approval",
                    "needs_review",
                )
                and not insufficient_balance
            ):

                balance.pending_reserved_days = round_days(
                    decimal_value(balance.pending_reserved_days)
                    + requested_amount
                )

            balance.available_days = round_days(
                decimal_value(balance.opening_days)
                + decimal_value(balance.accrued_days)
                + decimal_value(balance.adjustment_days)
                - decimal_value(balance.approved_used_days)
                - decimal_value(balance.pending_reserved_days)
            )

            balance.as_of_date = AS_OF_DATE

            total_audits += audit_sequence - 1

            # --------------------------------------------------
            # GROUND TRUTH LABEL
            # --------------------------------------------------

            labels.append({
                "leave_request_id": request_id,
                "employee_id": employee.employee_id,
                "country_code": employee.country_code,
                "leave_policy_id": policy.leave_policy_id,
                "business_days": business_days,
                "simulated_status": status,
                "rule_set_code": (
                    rules[0].rule_set_code if rules else ""
                ),
                "approval_steps_required": len(rules),
                "edge_case_type": (
                    "insufficient_balance"
                    if insufficient_balance
                    else "manual_review"
                    if status == "needs_review"
                    else ""
                ),
                "expected_outcome": status,
            })

        # --------------------------------------------------
        # SAVE EVERYTHING
        # --------------------------------------------------

        session.commit()

        GROUND_TRUTH_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        labels_path = (
            GROUND_TRUTH_DIR / "leave_request_labels.csv"
        )

        with open(
            labels_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(labels[0].keys()),
            )

            writer.writeheader()
            writer.writerows(labels)

        print("\n" + "=" * 50)
        print("LEAVE TRANSACTION GENERATION SUCCESSFUL")
        print("=" * 50)

        print("Leave requests:", len(plans))
        print("Approval steps:", total_steps)
        print("Audit events:", total_audits)

        print("\nRequest status distribution:")

        for status, count in sorted(status_counter.items()):
            print(f"{status}: {count}")

        print("\nGround truth file:")
        print(labels_path)

        print("\nLeave transaction generation completed!")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    generate_leave_transactions()
