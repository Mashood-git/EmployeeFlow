
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class ApprovalDecisionRequest(BaseModel):

    actor_employee_id: str = Field(
        min_length=1,
        max_length=20,
    )

    decision: Literal["approve", "reject"]

    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("actor_employee_id")
    @classmethod
    def normalize_employee_id(cls, value):
        return value.strip().upper()

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        if value is not None:
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_rejection_reason(self):

        if self.decision == "reject" and not self.reason:
            raise ValueError(
                "A reason is required when rejecting a request."
            )

        return self
