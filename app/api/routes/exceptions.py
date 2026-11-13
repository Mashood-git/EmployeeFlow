from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.exception_service import detect_exceptions

router = APIRouter()


@router.get("/")
def get_exceptions(
    exception_type: str | None = None,
    severity: str | None = None,
    country_code: str | None = None,
    db: Session = Depends(get_db)
):
    exceptions = detect_exceptions(db)

    if exception_type:
        exceptions = [
            item for item in exceptions
            if item["exception_type"] == exception_type
        ]

    if severity:
        exceptions = [
            item for item in exceptions
            if item["severity"] == severity
        ]

    if country_code:
        exceptions = [
            item for item in exceptions
            if item["country_code"] == country_code
        ]

    return {
        "total": len(exceptions),
        "items": exceptions
    }