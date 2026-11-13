from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


def run_query(db: Session, sql: str):
    result = db.execute(text(sql)).mappings().all()
    return [dict(row) for row in result]


def add_exceptions(items, rows, exception_type, severity, entity_type):
    for row in rows:
        items.append({
            "exception_id": (
                f"{exception_type}:"
                f"{row['entity_id']}:"
                f"{row.get('related_id') or ''}"
            ),
            "exception_type": exception_type,
            "severity": severity,
            "entity_type": entity_type,
            "entity_id": row["entity_id"],
            "related_id": row.get("related_id"),
            "employee_id": row.get("employee_id"),
            "employee_name": row.get("employee_name"),
            "department": row.get("department"),
            "country_code": row.get("country_code"),
            "category": row.get("category"),
            "amount_minor": row.get("amount_minor"),
            "currency_code": row.get("currency_code"),
            "description": row["description"],
        })


def detect_exceptions(db: Session):
    """
    Detect business and policy exceptions using database records.
    Ground-truth labels are deliberately not used here.
    """

    items = []

    # 1. Expense claims without an assigned cost center.
    rows = run_query(db, """
        SELECT
            ec.expense_claim_id AS entity_id,
            NULL AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            ec.country_code,
            ec.primary_category AS category,
            ec.total_amount_minor AS amount_minor,
            ec.currency_code,
            'Expense claim has no assigned cost center.' AS description
        FROM expense_claims ec
        JOIN employees e
            ON e.employee_id = ec.employee_id
        WHERE ec.cost_center_id IS NULL
    """)
    add_exceptions(
        items, rows, "missing_cost_center", "medium", "expense_claim"
    )

    # 2. Required receipts that are missing or have incomplete metadata.
    rows = run_query(db, """
        SELECT
            ec.expense_claim_id AS entity_id,
            el.expense_line_id AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            ec.country_code,
            el.category,
            el.amount_minor,
            ec.currency_code,
            'A required receipt or its verification metadata is missing.'
                AS description
        FROM expense_lines el
        JOIN expense_claims ec
            ON ec.expense_claim_id = el.expense_claim_id
        JOIN employees e
            ON e.employee_id = ec.employee_id
        JOIN expense_policies ep
            ON ep.expense_policy_id = el.expense_policy_id
        WHERE ep.receipt_required = 1
          AND el.amount_minor >= COALESCE(ep.receipt_threshold_minor, 0)
          AND (
              el.receipt_filename IS NULL
              OR TRIM(el.receipt_filename) = ''
              OR el.receipt_sha256 IS NULL
          )
    """)
    add_exceptions(
        items, rows, "missing_receipt", "high", "expense_claim"
    )

    # 3. Receipt hashes reused across expense lines.
    rows = run_query(db, """
        SELECT
            ec.expense_claim_id AS entity_id,
            el.expense_line_id AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            ec.country_code,
            el.category,
            el.amount_minor,
            ec.currency_code,
            'Receipt hash is used by more than one expense line.'
                AS description
        FROM expense_lines el
        JOIN expense_claims ec
            ON ec.expense_claim_id = el.expense_claim_id
        JOIN employees e
            ON e.employee_id = ec.employee_id
        WHERE el.receipt_sha256 IS NOT NULL
          AND el.receipt_sha256 IN (
              SELECT receipt_sha256
              FROM expense_lines
              WHERE receipt_sha256 IS NOT NULL
              GROUP BY receipt_sha256
              HAVING COUNT(*) > 1
          )
    """)
    add_exceptions(
        items, rows, "duplicate_receipt", "high", "expense_claim"
    )

    # 4. Individual expense lines exceeding their policy limit.
    rows = run_query(db, """
        SELECT
            ec.expense_claim_id AS entity_id,
            el.expense_line_id AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            ec.country_code,
            el.category,
            el.amount_minor,
            ec.currency_code,
            'Expense line exceeds the configured per-item limit.'
                AS description
        FROM expense_lines el
        JOIN expense_claims ec
            ON ec.expense_claim_id = el.expense_claim_id
        JOIN employees e
            ON e.employee_id = ec.employee_id
        JOIN expense_policies ep
            ON ep.expense_policy_id = el.expense_policy_id
        WHERE ep.per_item_limit_minor IS NOT NULL
          AND el.amount_minor > ep.per_item_limit_minor
    """)
    add_exceptions(
        items, rows, "per_item_limit_breach", "high", "expense_claim"
    )

    # 5. Total amount for a category within a claim exceeds its policy limit.
    rows = run_query(db, """
        SELECT
            ec.expense_claim_id AS entity_id,
            NULL AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            ec.country_code,
            el.category,
            SUM(el.amount_minor) AS amount_minor,
            ec.currency_code,
            'Claim category total exceeds the configured claim limit.'
                AS description
        FROM expense_lines el
        JOIN expense_claims ec
            ON ec.expense_claim_id = el.expense_claim_id
        JOIN employees e
            ON e.employee_id = ec.employee_id
        JOIN expense_policies ep
            ON ep.expense_policy_id = el.expense_policy_id
        WHERE ep.claim_limit_minor IS NOT NULL
        GROUP BY
            ec.expense_claim_id,
            ec.employee_id,
            e.first_name,
            e.last_name,
            e.department,
            ec.country_code,
            ec.currency_code,
            el.category,
            ep.claim_limit_minor
        HAVING SUM(el.amount_minor) > ep.claim_limit_minor
    """)
    add_exceptions(
        items, rows, "claim_limit_breach", "high", "expense_claim"
    )

    # 6. Expense dates outside the employee's employment period.
    rows = run_query(db, """
        SELECT
            ec.expense_claim_id AS entity_id,
            el.expense_line_id AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            ec.country_code,
            el.category,
            el.amount_minor,
            ec.currency_code,
            'Expense date falls outside the employee employment period.'
                AS description
        FROM expense_lines el
        JOIN expense_claims ec
            ON ec.expense_claim_id = el.expense_claim_id
        JOIN employees e
            ON e.employee_id = ec.employee_id
        WHERE date(el.expense_date) < date(e.hire_date)
           OR (
               e.termination_date IS NOT NULL
               AND date(el.expense_date) > date(e.termination_date)
           )
    """)
    add_exceptions(
        items, rows, "out_of_employment_dates", "high", "expense_claim"
    )

    # 7. Negative available leave balances.
    rows = run_query(db, """
        SELECT
            lb.leave_balance_id AS entity_id,
            NULL AS related_id,
            lb.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.country_code,
            NULL AS category,
            NULL AS amount_minor,
            NULL AS currency_code,
            'Employee has a negative available leave balance.'
                AS description
        FROM leave_balances lb
        JOIN employees e
            ON e.employee_id = lb.employee_id
        WHERE lb.available_days < 0
    """)
    add_exceptions(
        items, rows, "negative_leave_balance", "high", "leave_balance"
    )

    # 8. Overlapping approved leave for the same employee.
    rows = run_query(db, """
        SELECT
            a.leave_request_id AS entity_id,
            b.leave_request_id AS related_id,
            a.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.country_code,
            NULL AS category,
            NULL AS amount_minor,
            NULL AS currency_code,
            'Two approved leave requests overlap for the same employee.'
                AS description
        FROM leave_requests a
        JOIN leave_requests b
            ON a.employee_id = b.employee_id
           AND a.leave_request_id < b.leave_request_id
           AND a.start_date <= b.end_date
           AND a.end_date >= b.start_date
        JOIN employees e
            ON e.employee_id = a.employee_id
        WHERE a.status = 'approved'
          AND b.status = 'approved'
    """)
    add_exceptions(
        items, rows, "overlapping_approved_leave", "high", "leave_request"
    )

    # 9. Employees approving their own requests.
    rows = run_query(db, """
        SELECT
            aps.approval_step_id AS entity_id,
            lr.leave_request_id AS related_id,
            lr.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.country_code,
            NULL AS category,
            NULL AS amount_minor,
            NULL AS currency_code,
            'Employee approved their own leave request.'
                AS description
        FROM approval_steps aps
        JOIN leave_requests lr
            ON lr.leave_request_id = aps.leave_request_id
        JOIN employees e
            ON e.employee_id = lr.employee_id
        WHERE aps.approver_employee_id = lr.employee_id
          AND aps.status = 'approved'
    """)
    add_exceptions(
        items, rows, "self_approval", "critical", "approval_step"
    )

    rows = run_query(db, """
        SELECT
            aps.approval_step_id AS entity_id,
            ec.expense_claim_id AS related_id,
            ec.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.country_code,
            ec.primary_category AS category,
            ec.total_amount_minor AS amount_minor,
            ec.currency_code,
            'Employee approved their own expense claim.'
                AS description
        FROM approval_steps aps
        JOIN expense_claims ec
            ON ec.expense_claim_id = aps.expense_claim_id
        JOIN employees e
            ON e.employee_id = ec.employee_id
        WHERE aps.approver_employee_id = ec.employee_id
          AND aps.status = 'approved'
    """)
    add_exceptions(
        items, rows, "self_approval", "critical", "approval_step"
    )

    return items