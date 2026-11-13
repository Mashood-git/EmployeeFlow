"""Validate EmployeeFlow expense transactions and their ground-truth labels.

Run from the EmployeeFlow project root:
    python -m scripts.validate_expense_transactions

This script is read-only. It does not modify the database or regenerate data.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from app.db.session import SessionLocal
from app.models import (
    ApprovalRule,
    ApprovalStep,
    AuditEvent,
    CostCenter,
    Employee,
    ExpenseClaim,
    ExpenseLine,
    ExpensePolicy,
    Reimbursement,
)

EXPECTED_COUNTS = {
    "claims": 1000,
    "lines": 5467,
    "approval_steps": 1069,
    "reimbursements": 382,
    "audit_events": 5227,
    "claim_labels": 1000,
    "line_labels": 5467,
}

EXPECTED_EDGE_COUNTS = {
    "duplicate_receipt": 18,
    "missing_cost_center": 26,
    "missing_receipt": 18,
    "out_of_employment_dates": 8,
    "per_item_limit_breach": 18,
    "policy_limit_breach": 18,
    "split_claim_candidate": 40,
}

VALID_CLAIM_STATUSES = {
    "draft",
    "submitted",
    "pending_approval",
    "needs_review",
    "approved",
    "rejected",
    "cancelled",
}
VALID_STEP_STATUSES = {"pending", "approved", "rejected", "skipped"}
VALID_REIMBURSEMENT_STATUSES = {
    "pending_payment",
    "paid",
    "failed",
    "cancelled",
}
AS_OF_DATE = date(2026, 11, 11)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Ground-truth file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def active_on_day(record, start_attr: str, end_attr: str, day: date) -> bool:
    start = getattr(record, start_attr)
    end = getattr(record, end_attr)
    return start <= day and (end is None or end >= day)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    ground_truth = project_root / "data" / "ground_truth"

    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    db = SessionLocal()
    try:
        claims = db.query(ExpenseClaim).order_by(ExpenseClaim.expense_claim_id).all()
        lines = db.query(ExpenseLine).order_by(ExpenseLine.expense_line_id).all()
        steps = (
            db.query(ApprovalStep)
            .filter(ApprovalStep.expense_claim_id.isnot(None))
            .order_by(ApprovalStep.expense_claim_id, ApprovalStep.step_order)
            .all()
        )
        reimbursements = db.query(Reimbursement).all()
        audits = (
            db.query(AuditEvent)
            .filter(AuditEvent.audit_event_id.like("AUD-EXP-2026-%"))
            .all()
        )
        employees = db.query(Employee).all()
        policies = db.query(ExpensePolicy).all()
        rules = (
            db.query(ApprovalRule)
            .filter(ApprovalRule.request_type == "expense")
            .all()
        )
        cost_centers = db.query(CostCenter).all()

        claim_labels = read_csv(ground_truth / "expense_claim_labels.csv")
        line_labels = read_csv(ground_truth / "expense_line_labels.csv")
        scenarios = read_csv(ground_truth / "expense_control_test_scenarios.csv")

        employee_by_id = {item.employee_id: item for item in employees}
        policy_by_id = {item.expense_policy_id: item for item in policies}
        rule_by_id = {item.approval_rule_id: item for item in rules}
        center_by_id = {item.cost_center_id: item for item in cost_centers}
        claim_by_id = {item.expense_claim_id: item for item in claims}
        line_by_id = {item.expense_line_id: item for item in lines}
        step_by_id = {item.approval_step_id: item for item in steps}
        reimbursement_by_id = {
            item.reimbursement_id: item for item in reimbursements
        }

        lines_by_claim: dict[str, list[ExpenseLine]] = defaultdict(list)
        for line in lines:
            lines_by_claim[line.expense_claim_id].append(line)

        steps_by_claim: dict[str, list[ApprovalStep]] = defaultdict(list)
        for step in steps:
            steps_by_claim[step.expense_claim_id].append(step)

        reimbursements_by_claim: dict[str, list[Reimbursement]] = defaultdict(list)
        for reimbursement in reimbursements:
            reimbursements_by_claim[reimbursement.expense_claim_id].append(
                reimbursement
            )

        claim_label_by_id = {
            row["expense_claim_id"]: row for row in claim_labels
        }
        line_label_by_id = {
            row["expense_line_id"]: row for row in line_labels
        }

        print("\n--- BASIC COUNTS ---")
        actual_counts = {
            "claims": len(claims),
            "lines": len(lines),
            "approval_steps": len(steps),
            "reimbursements": len(reimbursements),
            "audit_events": len(audits),
            "claim_labels": len(claim_labels),
            "line_labels": len(line_labels),
        }
        for key, actual in actual_counts.items():
            expected = EXPECTED_COUNTS[key]
            print(f"{key.replace('_', ' ').title()}: {actual:,}")
            check(
                actual == expected,
                f"{key}: expected {expected}, found {actual}",
            )
        print(f"Control test scenarios: {len(scenarios)}")
        check(
            len(scenarios) == 20,
            f"Expected 20 control test scenarios, found {len(scenarios)}",
        )

        print("\n--- CLAIM STATUS DISTRIBUTION ---")
        status_counts = Counter(claim.status for claim in claims)
        for status, count in sorted(status_counts.items()):
            print(f"{status}: {count}")
        check(
            set(status_counts).issubset(VALID_CLAIM_STATUSES),
            "One or more claims have an invalid status",
        )

        print("\n--- GROUND-TRUTH EDGE-CASE COUNTS ---")
        edge_counts: Counter[str] = Counter()
        for row in claim_labels:
            for edge in filter(None, row["edge_case_type"].split(";")):
                edge_counts[edge] += 1
        for edge, expected in EXPECTED_EDGE_COUNTS.items():
            actual = edge_counts[edge]
            print(f"{edge}: {actual}")
            check(
                actual == expected,
                f"Ground-truth edge count for {edge}: expected {expected}, found {actual}",
            )

        # Primary-key and ground-truth coverage.
        check(len(claim_by_id) == len(claims), "Duplicate expense claim IDs found")
        check(len(line_by_id) == len(lines), "Duplicate expense line IDs found")
        check(len(step_by_id) == len(steps), "Duplicate expense approval step IDs found")
        check(
            set(claim_label_by_id) == set(claim_by_id),
            "Claim ground-truth IDs do not exactly match database claim IDs",
        )
        check(
            set(line_label_by_id) == set(line_by_id),
            "Line ground-truth IDs do not exactly match database line IDs",
        )

        # Build the configured rule set that should apply to each claim.
        rules_by_country_category: dict[tuple[str, str], list[ApprovalRule]] = (
            defaultdict(list)
        )
        for rule in rules:
            if rule.category:
                rules_by_country_category[(rule.country_code, rule.category)].append(
                    rule
                )

        print("\n--- CLAIM, LINE, POLICY AND EMPLOYMENT CHECKS ---")
        for claim in claims:
            claim_id = claim.expense_claim_id
            employee = employee_by_id.get(claim.employee_id)
            claim_lines = lines_by_claim.get(claim_id, [])
            label = claim_label_by_id.get(claim_id)

            check(employee is not None, f"{claim_id}: employee does not exist")
            check(bool(claim_lines), f"{claim_id}: claim has no expense lines")
            check(
                1 <= len(claim_lines) <= 10,
                f"{claim_id}: expected 1-10 lines, found {len(claim_lines)}",
            )
            check(
                claim.status in VALID_CLAIM_STATUSES,
                f"{claim_id}: invalid claim status {claim.status}",
            )
            check(
                claim.expense_start_date <= claim.expense_end_date,
                f"{claim_id}: expense start date is after end date",
            )
            check(
                claim.total_amount_minor > 0,
                f"{claim_id}: total amount must be positive",
            )

            if employee is not None:
                check(
                    claim.country_code == employee.country_code,
                    f"{claim_id}: claim country differs from employee country",
                )

            if claim.cost_center_id is not None:
                center = center_by_id.get(claim.cost_center_id)
                check(
                    center is not None,
                    f"{claim_id}: cost center {claim.cost_center_id} does not exist",
                )
                if center is not None:
                    check(
                        center.country_code == claim.country_code,
                        f"{claim_id}: cost center country mismatch",
                    )

            ordered_lines = sorted(claim_lines, key=lambda item: item.line_number)
            check(
                [item.line_number for item in ordered_lines]
                == list(range(1, len(ordered_lines) + 1)),
                f"{claim_id}: line numbers are not consecutive from 1",
            )
            if claim_lines:
                line_total = sum(item.amount_minor for item in claim_lines)
                check(
                    line_total == claim.total_amount_minor,
                    f"{claim_id}: claim total {claim.total_amount_minor} "
                    f"does not equal line sum {line_total}",
                )
                dates = [item.expense_date for item in claim_lines]
                check(
                    min(dates) == claim.expense_start_date
                    and max(dates) == claim.expense_end_date,
                    f"{claim_id}: claim date range does not match line dates",
                )
                check(
                    all(item.expense_date <= AS_OF_DATE for item in claim_lines),
                    f"{claim_id}: expense date is after dataset as-of date",
                )

            has_out_of_employment_label = (
                label is not None
                and "out_of_employment_dates"
                in label["edge_case_type"].split(";")
            )
            if employee is not None:
                outside_employment = any(
                    item.expense_date < employee.hire_date
                    or (
                        employee.termination_date is not None
                        and item.expense_date > employee.termination_date
                    )
                    for item in claim_lines
                )
                check(
                    outside_employment == has_out_of_employment_label,
                    f"{claim_id}: employment-date anomaly does not match ground truth",
                )

            missing_cost_center_label = (
                label is not None
                and "missing_cost_center" in label["edge_case_type"].split(";")
            )
            check(
                (claim.cost_center_id is None) == missing_cost_center_label,
                f"{claim_id}: missing cost center does not match ground truth",
            )

            for line in claim_lines:
                policy = policy_by_id.get(line.expense_policy_id)
                check(
                    policy is not None,
                    f"{line.expense_line_id}: expense policy does not exist",
                )
                if policy is not None:
                    check(
                        policy.country_code == claim.country_code,
                        f"{line.expense_line_id}: policy country mismatch",
                    )
                    check(
                        policy.currency_code == claim.currency_code,
                        f"{line.expense_line_id}: policy currency mismatch",
                    )
                    check(
                        policy.category == line.category == claim.primary_category,
                        f"{line.expense_line_id}: category mismatch",
                    )
                    check(
                        active_on_day(
                            policy,
                            "effective_start_date",
                            "effective_end_date",
                            line.expense_date,
                        ),
                        f"{line.expense_line_id}: policy not effective on expense date",
                    )
                    check(
                        line.amount_minor <= policy.per_item_limit_minor
                        or (
                            label is not None
                            and "per_item_limit_breach"
                            in label["edge_case_type"].split(";")
                        ),
                        f"{line.expense_line_id}: unlabelled per-item limit breach",
                    )
                check(
                    line.amount_minor > 0,
                    f"{line.expense_line_id}: line amount must be positive",
                )
                check(
                    line.expense_date >= claim.expense_start_date
                    and line.expense_date <= claim.expense_end_date,
                    f"{line.expense_line_id}: line date outside claim date range",
                )

                receipt_fields = (
                    line.receipt_filename,
                    line.receipt_sha256,
                    line.receipt_mime_type,
                    line.receipt_uploaded_at,
                )
                if line.receipt_sha256 is None:
                    check(
                        all(value is None for value in receipt_fields),
                        f"{line.expense_line_id}: incomplete missing-receipt metadata",
                    )
                else:
                    check(
                        all(value is not None for value in receipt_fields),
                        f"{line.expense_line_id}: receipt metadata is incomplete",
                    )

            if label is not None:
                check(
                    label["employee_id"] == claim.employee_id,
                    f"{claim_id}: ground-truth employee mismatch",
                )
                check(
                    label["status"] == claim.status,
                    f"{claim_id}: ground-truth status mismatch",
                )
                check(
                    int(label["total_amount_minor"]) == claim.total_amount_minor,
                    f"{claim_id}: ground-truth amount mismatch",
                )
                check(
                    int(label["line_count"]) == len(claim_lines),
                    f"{claim_id}: ground-truth line count mismatch",
                )

        # Line-level labels and receipt anomaly reconciliation.
        print("\n--- RECEIPT AND LINE-LABEL CHECKS ---")
        missing_receipts = 0
        for line in lines:
            label = line_label_by_id.get(line.expense_line_id)
            if label is None:
                continue
            is_missing = line.receipt_sha256 is None
            missing_receipts += int(is_missing)
            check(
                (label["missing_receipt"].lower() == "true") == is_missing,
                f"{line.expense_line_id}: missing-receipt label mismatch",
            )
            policy = policy_by_id.get(line.expense_policy_id)
            if policy is not None:
                breach = line.amount_minor > policy.per_item_limit_minor
                check(
                    (label["per_item_limit_breach"].lower() == "true") == breach,
                    f"{line.expense_line_id}: per-item breach label mismatch",
                )
            check(
                label["expense_claim_id"] == line.expense_claim_id,
                f"{line.expense_line_id}: line-label claim ID mismatch",
            )

        receipt_hash_groups: dict[str, list[ExpenseLine]] = defaultdict(list)
        for line in lines:
            if line.receipt_sha256:
                receipt_hash_groups[line.receipt_sha256].append(line)
        duplicate_hash_lines = {
            line.expense_line_id
            for group in receipt_hash_groups.values()
            if len(group) > 1
            for line in group
        }
        labelled_duplicate_lines = {
            row["expense_line_id"]
            for row in line_labels
            if row["duplicate_receipt"].lower() == "true"
        }
        check(
            len(labelled_duplicate_lines) == EXPECTED_EDGE_COUNTS["duplicate_receipt"],
            "Unexpected number of duplicate receipt line labels",
        )
        check(
            labelled_duplicate_lines.issubset(duplicate_hash_lines),
            "One or more duplicate receipt labels have no matching duplicate hash",
        )
        check(
            missing_receipts == EXPECTED_EDGE_COUNTS["missing_receipt"],
            f"Expected 18 missing receipt lines, found {missing_receipts}",
        )

        # Approval routing and workflow state checks.
        print("\n--- APPROVAL WORKFLOW CHECKS ---")
        for claim in claims:
            claim_id = claim.expense_claim_id
            claim_steps = sorted(
                steps_by_claim.get(claim_id, []),
                key=lambda item: item.step_order,
            )
            label = claim_label_by_id.get(claim_id)
            expected_step_statuses = {
                "approved": {"approved"},
                "pending_approval": {"pending"},
                "cancelled": {"skipped"},
            }

            if claim.status in {"pending_approval", "approved", "rejected", "cancelled"}:
                check(
                    len(claim_steps) > 0,
                    f"{claim_id}: workflow status requires approval steps",
                )
            else:
                check(
                    len(claim_steps) == 0,
                    f"{claim_id}: {claim.status} claim unexpectedly has approval steps",
                )

            if claim.status in expected_step_statuses:
                check(
                    all(step.status in expected_step_statuses[claim.status]
                        for step in claim_steps),
                    f"{claim_id}: approval step statuses do not match claim status",
                )
            elif claim.status == "rejected":
                statuses = [step.status for step in claim_steps]
                check(
                    statuses.count("rejected") == 1,
                    f"{claim_id}: rejected claim must have exactly one rejected step",
                )
                if "rejected" in statuses:
                    rejected_at = statuses.index("rejected")
                    check(
                        all(s == "approved" for s in statuses[:rejected_at])
                        and all(s == "skipped" for s in statuses[rejected_at + 1:]),
                        f"{claim_id}: rejected workflow has invalid step sequence",
                    )

            if claim.status in {"approved", "rejected", "cancelled"}:
                check(
                    claim.final_decision_at is not None,
                    f"{claim_id}: final decision timestamp is missing",
                )
            else:
                check(
                    claim.final_decision_at is None,
                    f"{claim_id}: unexpected final decision timestamp",
                )

            check(
                (claim.status == "draft") == (claim.submitted_at is None),
                f"{claim_id}: submitted timestamp does not match draft status",
            )
            if claim.submitted_at is not None:
                check(
                    claim.created_at <= claim.submitted_at,
                    f"{claim_id}: submitted_at precedes created_at",
                )
            if claim.final_decision_at is not None and claim.submitted_at is not None:
                check(
                    claim.final_decision_at >= claim.submitted_at,
                    f"{claim_id}: final decision precedes submission",
                )

            # Determine the approval rule set from configured country/category/amount rules.
            candidates = rules_by_country_category.get(
                (claim.country_code, claim.primary_category), []
            )
            matching_by_set: dict[str, list[ApprovalRule]] = defaultdict(list)
            for rule in candidates:
                if not rule.is_active or not active_on_day(
                    rule,
                    "effective_start_date",
                    "effective_end_date",
                    claim.expense_start_date,
                ):
                    continue
                minimum = (
                    rule.min_amount_minor
                    if rule.min_amount_minor is not None
                    else 0
                )
                maximum = rule.max_amount_minor
                if claim.total_amount_minor >= minimum and (
                    maximum is None or claim.total_amount_minor <= maximum
                ):
                    matching_by_set[rule.rule_set_code].append(rule)

            check(
                len(matching_by_set) == 1,
                f"{claim_id}: expected exactly one matching approval rule set, "
                f"found {len(matching_by_set)}",
            )
            expected_rules: list[ApprovalRule] = []
            expected_rule_set = ""
            if matching_by_set:
                expected_rule_set = sorted(matching_by_set)[0]
                expected_rules = sorted(
                    matching_by_set[expected_rule_set],
                    key=lambda item: item.step_order,
                )

            if label is not None:
                check(
                    label["approval_rule_set"] == expected_rule_set,
                    f"{claim_id}: ground-truth approval rule set mismatch",
                )
                check(
                    int(label["approval_step_count"]) == len(claim_steps),
                    f"{claim_id}: ground-truth approval step count mismatch",
                )

            if claim_steps:
                check(
                    len(claim_steps) == len(expected_rules),
                    f"{claim_id}: approval step count does not match configured rules",
                )
                for index, step in enumerate(claim_steps):
                    approver = employee_by_id.get(step.approver_employee_id)
                    rule = rule_by_id.get(step.approval_rule_id)
                    check(
                        step.expense_claim_id == claim_id
                        and step.leave_request_id is None,
                        f"{step.approval_step_id}: incorrect request linkage",
                    )
                    check(
                        step.status in VALID_STEP_STATUSES,
                        f"{step.approval_step_id}: invalid step status",
                    )
                    check(
                        approver is not None,
                        f"{step.approval_step_id}: approver does not exist",
                    )
                    if approver is not None:
                        check(
                            approver.employee_id != claim.employee_id,
                            f"{step.approval_step_id}: self-approval detected",
                        )
                        check(
                            approver.country_code == claim.country_code,
                            f"{step.approval_step_id}: approver country mismatch",
                        )
                        check(
                            approver.employment_status == "active",
                            f"{step.approval_step_id}: approver is not active",
                        )
                    check(
                        rule is not None,
                        f"{step.approval_step_id}: approval rule does not exist",
                    )
                    if rule is not None:
                        check(
                            rule.request_type == "expense"
                            and rule.country_code == claim.country_code
                            and rule.category == claim.primary_category,
                            f"{step.approval_step_id}: approval rule does not match claim",
                        )
                        check(
                            rule.min_amount_minor is None
                            or claim.total_amount_minor >= rule.min_amount_minor,
                            f"{step.approval_step_id}: amount below rule minimum",
                        )
                        check(
                            rule.max_amount_minor is None
                            or claim.total_amount_minor <= rule.max_amount_minor,
                            f"{step.approval_step_id}: amount above rule maximum",
                        )
                        if approver is not None:
                            if rule.approver_type == "role":
                                check(
                                    approver.system_role == rule.approver_role,
                                    f"{step.approval_step_id}: role approver mismatch",
                                )
                            elif rule.approver_type == "employee":
                                check(
                                    approver.employee_id == rule.approver_employee_id,
                                    f"{step.approval_step_id}: employee approver mismatch",
                                )
                            elif rule.approver_type == "manager":
                                check(
                                    approver.system_role == "manager",
                                    f"{step.approval_step_id}: manager approver role mismatch",
                                )
                    if index < len(expected_rules):
                        check(
                            step.approval_rule_id == expected_rules[index].approval_rule_id,
                            f"{step.approval_step_id}: wrong approval rule or step order",
                        )

        # Reimbursement integrity.
        print("\n--- REIMBURSEMENT CHECKS ---")
        approved_claims = {
            claim.expense_claim_id: claim
            for claim in claims
            if claim.status == "approved"
        }
        check(
            len(reimbursements) == len(approved_claims),
            "Reimbursement count does not equal approved claim count",
        )
        for claim_id, claim in claim_by_id.items():
            claim_reimbursements = reimbursements_by_claim.get(claim_id, [])
            if claim.status == "approved":
                check(
                    len(claim_reimbursements) == 1,
                    f"{claim_id}: approved claim must have exactly one reimbursement",
                )
            else:
                check(
                    len(claim_reimbursements) == 0,
                    f"{claim_id}: non-approved claim has a reimbursement",
                )

        for reimbursement in reimbursements:
            claim = claim_by_id.get(reimbursement.expense_claim_id)
            check(
                claim is not None and claim.status == "approved",
                f"{reimbursement.reimbursement_id}: reimbursement is not linked "
                "to an approved claim",
            )
            if claim is not None:
                check(
                    reimbursement.amount_minor == claim.total_amount_minor,
                    f"{reimbursement.reimbursement_id}: amount mismatch",
                )
                check(
                    reimbursement.currency_code == claim.currency_code,
                    f"{reimbursement.reimbursement_id}: currency mismatch",
                )
                check(
                    reimbursement.created_at >= claim.final_decision_at,
                    f"{reimbursement.reimbursement_id}: created before final approval",
                )
                creator = employee_by_id.get(
                    reimbursement.created_by_employee_id
                )
                check(
                    creator is not None
                    and creator.system_role == "finance_admin"
                    and creator.country_code == claim.country_code
                    and creator.employment_status == "active",
                    f"{reimbursement.reimbursement_id}: invalid reimbursement creator",
                )
            check(
                reimbursement.status in VALID_REIMBURSEMENT_STATUSES,
                f"{reimbursement.reimbursement_id}: invalid reimbursement status",
            )
            if reimbursement.status == "paid":
                check(
                    reimbursement.paid_at is not None
                    and reimbursement.payment_reference is not None,
                    f"{reimbursement.reimbursement_id}: paid reimbursement "
                    "is missing payment details",
                )
            elif reimbursement.status == "failed":
                check(
                    reimbursement.paid_at is None
                    and reimbursement.payment_reference is not None,
                    f"{reimbursement.reimbursement_id}: failed reimbursement "
                    "has invalid payment details",
                )
            else:
                check(
                    reimbursement.paid_at is None,
                    f"{reimbursement.reimbursement_id}: unpaid reimbursement "
                    "has a paid_at timestamp",
                )

        # Audit-event integrity.
        print("\n--- AUDIT EVENT CHECKS ---")
        for event in audits:
            if event.entity_type == "expense_claim":
                check(
                    event.entity_id in claim_by_id,
                    f"{event.audit_event_id}: audit references unknown expense claim",
                )
            elif event.entity_type == "approval_step":
                check(
                    event.entity_id in step_by_id,
                    f"{event.audit_event_id}: audit references unknown approval step",
                )
            elif event.entity_type == "reimbursement":
                check(
                    event.entity_id in reimbursement_by_id,
                    f"{event.audit_event_id}: audit references unknown reimbursement",
                )
            else:
                check(
                    False,
                    f"{event.audit_event_id}: unexpected expense audit entity type "
                    f"{event.entity_type}",
                )

        created_claim_events = {
            event.entity_id
            for event in audits
            if event.entity_type == "expense_claim"
            and event.event_type == "expense_claim_created"
        }
        check(
            created_claim_events == set(claim_by_id),
            "Every expense claim must have exactly one creation audit event",
        )

        # Scenario rows describe attempted actions; they must not have been inserted
        # as invalid approval/reimbursement records.
        scenario_types = Counter(row["scenario_type"] for row in scenarios)
        check(
            scenario_types["self_approval_attempt"] == 10
            and scenario_types["duplicate_reimbursement_attempt"] == 10,
            "Control scenarios must contain 10 self-approval and 10 "
            "duplicate-reimbursement attempts",
        )
        for row in scenarios:
            check(
                row["expense_claim_id"] in approved_claims,
                f"{row['scenario_id']}: scenario is not linked to an approved claim",
            )
            if row["scenario_type"] == "self_approval_attempt":
                check(
                    row["requester_employee_id"]
                    == row["proposed_approver_employee_id"],
                    f"{row['scenario_id']}: self-approval scenario is malformed",
                )

        print("\n--- VALIDATION RESULT ---")
        if errors:
            print(f"FAILED: {len(errors)} validation issue(s)")
            for error in errors[:60]:
                print(f" - {error}")
            if len(errors) > 60:
                print(f" ... and {len(errors) - 60} more issue(s)")
            sys.exit(1)

        print("All expense transaction validations passed!")
        print(f"{len(claims):,} claims verified.")
        print(f"{len(lines):,} expense lines verified.")
        print("Approval routing and workflow states verified.")
        print("Reimbursement eligibility and amounts verified.")
        print("Receipt metadata and edge-case labels verified.")
        print("Audit records and ground-truth files verified.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
