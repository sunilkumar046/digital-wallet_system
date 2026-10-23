
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SuspiciousActivityReviewRequest(BaseModel):
    status: Literal["REVIEWED", "RESOLVED"]
    review_notes: str = Field(min_length=3, max_length=2000)


class SuspiciousActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    transaction_id: int | None
    reason: str
    severity: str
    status: str
    details: str | None
    reviewed_by: int | None
    review_notes: str | None
    detected_at: datetime
    reviewed_at: datetime | None
