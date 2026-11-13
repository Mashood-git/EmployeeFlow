
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.db.session import DB_PATH
from app.models import ApprovalStep, ExpenseClaim, Reimbursement, AuditEvent
from app.schemas.approval import ApprovalDecisionRequest
from app.services.approval_service import process_approval_decision


TEST_DB_PATH = DB_PATH.parent / "employeeflow_expense_approval_test.db"

APPROVAL_STEP_ID = "APR-EXP-2026-000001-01"
CLAIM_ID = "EXP-2026-000001"
APPROVER_ID = "EMP-000322"


def main():
    # Create an isolated copy of the original database.
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    source = sqlite3.connect(str(DB_PATH))
    target = sqlite3.connect(str(TEST_DB_PATH))

    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    print("Created isolated test database:", TEST_DB_PATH)

    # Connect to the copied database.
    test_engine = create_engine(
        URL.create(
            drivername="sqlite",
            database=str(TEST_DB_PATH)
        ),
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestSession = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False
    )

    db = TestSession()

    try:
        claim = db.get(ExpenseClaim, CLAIM_ID)

        assert claim is not None, "Expense claim not found."
        assert claim.status == "pending_approval"

        print("\nBefore approval:")
        print("Claim status:", claim.status)
        print("Amount:", claim.total_amount_minor)
        print("Currency:", claim.currency_code)

        existing = (
            db.query(Reimbursement)
            .filter_by(expense_claim_id=CLAIM_ID)
            .first()
        )
        assert existing is None, "Reimbursement already exists."

        # Submit the decision as the assigned approver.
        payload = ApprovalDecisionRequest(
            actor_employee_id=APPROVER_ID,
            decision="approve",
            reason="Approved during isolated expense workflow test."
        )

        result = process_approval_decision(
            db=db,
            approval_step_id=APPROVAL_STEP_ID,
            payload=payload
        )

        print("\nService response:")
        print(result)

        db.expire_all()

        claim = db.get(ExpenseClaim, CLAIM_ID)
        approval = db.get(ApprovalStep, APPROVAL_STEP_ID)

        reimbursement = (
            db.query(Reimbursement)
            .filter_by(expense_claim_id=CLAIM_ID)
            .one()
        )

        print("\nAfter approval:")
        print("Claim status:", claim.status)
        print("Approval status:", approval.status)
        print("Reimbursement ID:", reimbursement.reimbursement_id)
        print("Reimbursement amount:", reimbursement.amount_minor)
        print("Reimbursement currency:", reimbursement.currency_code)
        print("Reimbursement status:", reimbursement.status)

        # Verify the approval and reimbursement.
        assert claim.status == "approved"
        assert approval.status == "approved"
        assert reimbursement.amount_minor == 9000
        assert reimbursement.currency_code == "USD"
        assert reimbursement.status == "pending_payment"

        # Verify that reimbursement creation was audited.
        audit_count = (
            db.query(AuditEvent)
            .filter_by(
                entity_type="reimbursement",
                entity_id=reimbursement.reimbursement_id
            )
            .count()
        )

        assert audit_count >= 1, "Reimbursement audit event missing."

        print("Reimbursement audit events:", audit_count)
        print("\nPASS: Expense approval and reimbursement tests passed.")
        print("Original database was not modified.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
        test_engine.dispose()


if __name__ == "__main__":
    main()
