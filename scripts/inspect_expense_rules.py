from app.db.session import SessionLocal
from app.models import ExpensePolicy, ApprovalRule

db = SessionLocal()

for model in (ExpensePolicy, ApprovalRule):
    print(f"\n{'=' * 70}")
    print(model.__name__.upper())
    print(f"{'=' * 70}")

    columns = [
        c.name for c in model.__table__.columns
        if c.name not in ("created_at", "updated_at")
    ]

    print(" | ".join(columns))

    for record in db.query(model).all():
        print(" | ".join(str(getattr(record, col)) for col in columns))

db.close()
