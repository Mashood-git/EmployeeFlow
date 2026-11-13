
from app.db.session import SessionLocal
from app.models import ApprovalStep, ExpenseClaim, Reimbursement


def main():
    db = SessionLocal()

    try:
        pending_steps = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.expense_claim_id.isnot(None),
                ApprovalStep.status == "pending"
            )
            .order_by(ApprovalStep.approval_step_id)
            .all()
        )

        found = 0

        for step in pending_steps:
            claim = db.get(ExpenseClaim, step.expense_claim_id)

            if claim is None:
                continue

            if claim.status not in ("submitted", "pending_approval"):
                continue

            all_steps = (
                db.query(ApprovalStep)
                .filter(
                    ApprovalStep.expense_claim_id == claim.expense_claim_id
                )
                .order_by(ApprovalStep.step_order)
                .all()
            )

            previous_steps = [
                item for item in all_steps
                if item.step_order < step.step_order
            ]

            previous_approved = all(
                item.status == "approved"
                for item in previous_steps
            )

            later_pending = any(
                item.step_order > step.step_order
                and item.status == "pending"
                for item in all_steps
            )

            reimbursement = (
                db.query(Reimbursement)
                .filter(
                    Reimbursement.expense_claim_id
                    == claim.expense_claim_id
                )
                .first()
            )

            if (
                previous_approved
                and not later_pending
                and reimbursement is None
            ):
                found += 1

                print(f"\nCandidate {found}")
                print("Approval ID:", step.approval_step_id)
                print("Expense Claim:", claim.expense_claim_id)
                print("Employee:", claim.employee_id)
                print("Approver:", step.approver_employee_id)
                print("Step:", step.step_order)
                print("Total steps:", len(all_steps))
                print("Claim status:", claim.status)
                print("Amount (minor units):", claim.total_amount_minor)
                print("Currency:", claim.currency_code)

                if found == 5:
                    break

        if found == 0:
            print("No suitable final expense approvals found.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
