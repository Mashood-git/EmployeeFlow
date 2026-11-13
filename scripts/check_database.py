
from sqlalchemy import text

from app.db.session import engine, DB_PATH


def check_database():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        print("Database connection:", result.scalar())

        foreign_keys = connection.execute(
            text("PRAGMA foreign_keys")
        ).scalar()

        print("Foreign keys enabled:", foreign_keys)

    print("Database location:", DB_PATH)
    print("Database foundation is working!")


if __name__ == "__main__":
    check_database()
