
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


# Find the root EmployeeFlow project directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Create the data directory if it doesn't exist
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database file location
DB_PATH = DATA_DIR / "employeeflow.db"

# SQLite database connection URL
DATABASE_URL = URL.create(
    drivername="sqlite",
    database=str(DB_PATH)
)

# Create the database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)


# Enable foreign key validation in SQLite
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create a database session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


# Database session dependency for FastAPI
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
