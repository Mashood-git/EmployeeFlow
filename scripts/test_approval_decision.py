
import sqlite3
from pathlib import Path
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.db.session import DB_PATH
from app.models import ApprovalStep, LeaveBalance, LeaveRequest, AuditEvent
from app.schemas.approval import ApprovalDecisionRequest
from app.services.approval_service import process_approval_decision


TEST_DB_PATH = DB_PATH.parent / "employeeflow_approval_test.db"

APPROVAL_STEP_ID = "APR-LVE-2026-000135-01"
REQUEST_ID = "LVE-2026-000135"
EMPLOYEE_ID = "EMP-000273"
POLICY_ID = "LP-IN-ANNUAL"


def main():
    # Create a fresh copy of the original database.
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

    # Connect SQLAlchemy to the test database.
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
        # Verify the starting state.
        balance = db.query(LeaveBalance).filter_by(
            employee_id=EMPLOYEE_ID,
            leave_policy_id=POLICY_ID,
            period_year=2026
        ).one()

        print("\nBefore approval:")
        print("Pending reserved:", balance.pending_reserved_days)
        print("Approved used:", balance.approved_used_days)
        print("Available:", balance.available_days)

        # Simulate the assigned approver approving the request.
        payload = ApprovalDecisionRequest(
            actor_employee_id="EMP-000015",
            decision="approve",
            reason="Approved during isolated workflow test."
        )

        result = process_approval_decision(
            db=db,
            approval_step_id=APPROVAL_STEP_ID,
            payload=payload
        )

        print("\nService response:")
        print(result)

        # Reload records after the service commits.
        db.expire_all()

        request = db.get(LeaveRequest, REQUEST_ID)
        approval = db.get(ApprovalStep, APPROVAL_STEP_ID)

        balance = db.query(LeaveBalance).filter_by(
            employee_id=EMPLOYEE_ID,
            leave_policy_id=POLICY_ID,
            period_year=2026
        ).one()

        print("\nAfter approval:")
        print("Request status:", request.status)
        print("Approval status:", approval.status)
        print("Pending reserved:", balance.pending_reserved_days)
        print("Approved used:", balance.approved_used_days)
        print("Available:", balance.available_days)

        # Verify expected results.
        assert request.status == "approved"
        assert approval.status == "approved"
        assert balance.pending_reserved_days == Decimal("0.00")
        assert balance.approved_used_days == Decimal("4.00")
        assert balance.available_days == Decimal("11.00")

        print("\nPASS: Approval workflow and leave balance tests passed.")
        print("Original database was not modified.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
        test_engine.dispose()


if __name__ == "__main__":
    main()
