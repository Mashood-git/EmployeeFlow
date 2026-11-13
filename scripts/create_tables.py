from app.db.base import Base
from app.db.session import engine

# Import models so SQLAlchemy registers their tables
from app.models import Employee, LeavePolicy, LeaveBalance


def create_tables():
    Base.metadata.create_all(bind=engine)

    print("Database tables created successfully!")

    print("\nRegistered tables:")
    for table_name in Base.metadata.tables:
        print("-", table_name)


if __name__ == "__main__":
    create_tables()