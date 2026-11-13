
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.db.session import SessionLocal
from app.models import (
    Employee,
    LeavePolicy,
    LeaveBalance,
    LeaveRequest,
    Holiday,
    ApprovalRule,
    ApprovalStep,
    AuditEvent,
)


def rounded(value):
    return Decimal(str(value or 0)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def validate_leave_transactions():
    with SessionLocal() as session:

        requests = session.query(LeaveRequest).all()
        steps = session.query(ApprovalStep).filter(
            ApprovalStep.leave_request_id.isnot(None)
        ).all()

        audits = session.query(AuditEvent).filter(
            AuditEvent.audit_event_id.like("AUD-LVE-2026-%")
        ).all()

        employees = {
            e.employee_id: e
            for e in session.query(Employee).all()
        }

        policies = {
            p.leave_policy_id: p
            for p in session.query(LeavePolicy).all()
        }

        rules = {
            r.approval_rule_id: r
            for r in session.query(ApprovalRule).all()
        }

        balances = session.query(LeaveBalance).filter(
            LeaveBalance.period_year == 2026
        ).all()

        holidays = defaultdict(set)

        for holiday in session.query(Holiday).all():
            holidays[holiday.country_code].add(
                holiday.holiday_date
            )

        steps_by_request = defaultdict(list)

        for step in steps:
            steps_by_request[step.leave_request_id].append(step)

        labels = {}

        import csv
        from pathlib import Path

        label_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "ground_truth"
            / "leave_request_labels.csv"
        )

        with open(label_path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                labels[row["leave_request_id"]] = row

        errors = []

        def check(condition, message):
            if not condition:
                errors.append(message)

        print("\n--- BASIC COUNTS ---")
        print("Leave requests:", len(requests))
        print("Approval steps:", len(steps))
        print("Audit events:", len(audits))
        print("Ground-truth labels:", len(labels))

        check(len(requests) == 800, "Expected 800 leave requests")
        check(len(labels) == 800, "Expected 800 ground-truth labels")
        check(len(steps) == 915, "Unexpected approval step count")
        check(len(audits) == 3715, "Unexpected audit event count")

        print("\n--- STATUS DISTRIBUTION ---")

        status_counts = Counter(r.status for r in requests)

        for status, count in sorted(status_counts.items()):
            print(f"{status}: {count}")

        # Check unique employee-policy combinations.
        pairs = [
            (r.employee_id, r.leave_policy_id)
            for r in requests
        ]

        check(
            len(pairs) == len(set(pairs)),
            "Duplicate employee-policy leave requests found",
        )

        # Check request dates and business-day calculations.
        for request in requests:

            employee = employees.get(request.employee_id)
            policy = policies.get(request.leave_policy_id)

            check(employee is not None, f"Missing employee: {request.leave_request_id}")
            check(policy is not None, f"Missing policy: {request.leave_request_id}")

            if employee is None or policy is None:
                continue

            check(
                request.start_date <= request.end_date,
                f"Invalid date order: {request.leave_request_id}",
            )

            check(
                request.start_date >= employee.hire_date,
                f"Leave before hire date: {request.leave_request_id}",
            )

            if employee.termination_date:
                check(
                    request.end_date <= employee.termination_date,
                    f"Leave after termination: {request.leave_request_id}",
                )

            check(
                employee.country_code == policy.country_code,
                f"Employee-policy country mismatch: {request.leave_request_id}",
            )

            calculated = 0
            current = request.start_date

            while current <= request.end_date:
                if (
                    current.weekday() < 5
                    and current not in holidays[employee.country_code]
                ):
                    calculated += 1

                from datetime import timedelta
                current += timedelta(days=1)

            check(
                rounded(request.business_days) == rounded(calculated),
                f"Business-day mismatch: {request.leave_request_id}",
            )

            check(
                request.leave_request_id in labels,
                f"Missing ground-truth label: {request.leave_request_id}",
            )

        # Check approval steps and approvers.
        for step in steps:

            request = next(
                (
                    r for r in requests
                    if r.leave_request_id == step.leave_request_id
                ),
                None,
            )

            if request is None:
                check(False, f"Missing leave request for {step.approval_step_id}")
                continue

            requester = employees[request.employee_id]
            approver = employees.get(step.approver_employee_id)
            rule = rules.get(step.approval_rule_id)

            check(
                step.expense_claim_id is None,
                f"Expense reference on leave approval: {step.approval_step_id}",
            )

            check(
                approver is not None,
                f"Missing approver: {step.approval_step_id}",
            )

            if approver:
                check(
                    approver.employee_id != requester.employee_id,
                    f"Self-approval detected: {step.approval_step_id}",
                )

                check(
                    approver.country_code == requester.country_code,
                    f"Cross-country approver: {step.approval_step_id}",
                )

            check(
                rule is not None and rule.request_type == "leave",
                f"Invalid approval rule: {step.approval_step_id}",
            )

            check(
                step.status in ("pending", "approved", "rejected", "skipped"),
                f"Invalid approval status: {step.approval_step_id}",
            )

        # Check workflow status consistency.
        for request in requests:

            request_steps = sorted(
                steps_by_request[request.leave_request_id],
                key=lambda s: s.step_order,
            )

            if request.status == "approved":
                check(
                    all(s.status == "approved" for s in request_steps),
                    f"Approved request has incomplete approvals: {request.leave_request_id}",
                )

            elif request.status == "pending_approval":
                check(
                    bool(request_steps)
                    and all(s.status == "pending" for s in request_steps),
                    f"Invalid pending workflow: {request.leave_request_id}",
                )

            elif request.status == "rejected":
                check(
                    any(s.status == "rejected" for s in request_steps),
                    f"Rejected request has no rejected step: {request.leave_request_id}",
                )

            elif request.status == "cancelled":
                check(
                    all(s.status == "skipped" for s in request_steps),
                    f"Cancelled request has non-skipped steps: {request.leave_request_id}",
                )

            elif request.status in ("draft", "submitted", "needs_review"):
                check(
                    len(request_steps) == 0,
                    f"Unexpected approval steps: {request.leave_request_id}",
                )

        # Reconcile balance arithmetic.
        print("\n--- LEAVE BALANCE RECONCILIATION ---")

        for balance in balances:

            expected = rounded(
                Decimal(str(balance.opening_days))
                + Decimal(str(balance.accrued_days))
                + Decimal(str(balance.adjustment_days))
                - Decimal(str(balance.approved_used_days))
                - Decimal(str(balance.pending_reserved_days))
            )

            actual = rounded(balance.available_days)

            check(
                expected == actual,
                f"Balance arithmetic mismatch: {balance.leave_balance_id}",
            )

        # Check aggregate usage against requests and labels.
        expected_used = defaultdict(Decimal)
        expected_reserved = defaultdict(Decimal)

        for request in requests:

            key = (request.employee_id, request.leave_policy_id)
            days = Decimal(str(request.business_days))

            if request.status == "approved":
                expected_used[key] += days

            elif request.status in (
                "submitted",
                "pending_approval",
                "needs_review",
            ):
                label = labels.get(request.leave_request_id, {})

                if label.get("edge_case_type") != "insufficient_balance":
                    expected_reserved[key] += days

        for balance in balances:

            key = (balance.employee_id, balance.leave_policy_id)

            check(
                rounded(balance.approved_used_days)
                == rounded(expected_used[key]),
                f"Approved usage mismatch: {balance.leave_balance_id}",
            )

            check(
                rounded(balance.pending_reserved_days)
                == rounded(expected_reserved[key]),
                f"Pending reservation mismatch: {balance.leave_balance_id}",
            )

        # Final results.
        print("\n--- VALIDATION RESULT ---")

        if errors:
            print(f"FAILED: {len(errors)} validation errors")

            for error in errors[:30]:
                print("ERROR:", error)

            raise SystemExit(1)

        print("All leave transaction validations passed!")
        print("800 requests verified.")
        print("Approval routing verified.")
        print("Audit records verified.")
        print("Leave balance arithmetic verified.")
        print("Ground-truth labels verified.")


if __name__ == "__main__":
    validate_leave_transactions()
