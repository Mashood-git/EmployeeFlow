
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all database models.

    Every database model (Employee, LeaveRequest,
    ExpenseClaim, etc.) will inherit from this class.
    """
    pass
