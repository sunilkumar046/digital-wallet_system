
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.database.database import get_db
from app.models.suspicious_activity import SuspiciousActivity
from app.models.user import User
from app.schemas.suspicious_activity import (
    SuspiciousActivityResponse,
    SuspiciousActivityReviewRequest,
)


router = APIRouter(
    prefix="/api/suspicious-activities",
    tags=["Suspicious Activity"],
)

STAFF_ROLES = ("Super Admin", "Admin", "Support Agent")


@router.get(
    "",
    response_model=list[SuspiciousActivityResponse],
)
def list_suspicious_activities(
    activity_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(OPEN|REVIEWED|RESOLVED)$",
    ),
    severity: str | None = Query(
        default=None,
        pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """List suspicious activities with optional filters and pagination."""
    query = select(SuspiciousActivity)

    if activity_status is not None:
        query = query.where(
            SuspiciousActivity.status == activity_status
        )

    if severity is not None:
        query = query.where(
            SuspiciousActivity.severity == severity
        )

    query = (
        query
        .order_by(SuspiciousActivity.detected_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(query).all())


@router.get(
    "/{activity_id}",
    response_model=SuspiciousActivityResponse,
)
def get_suspicious_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Retrieve a single suspicious-activity record."""
    activity = db.get(SuspiciousActivity, activity_id)

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suspicious activity not found",
        )

    return activity


@router.patch(
    "/{activity_id}/review",
    response_model=SuspiciousActivityResponse,
)
def review_suspicious_activity(
    activity_id: int,
    request: SuspiciousActivityReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """Record the staff member's review decision and notes."""
    activity = db.scalar(
        select(SuspiciousActivity)
        .where(SuspiciousActivity.id == activity_id)
        .with_for_update()
    )

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suspicious activity not found",
        )

    if activity.status == "RESOLVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This suspicious activity has already been resolved",
        )

    activity.status = request.status
    activity.reviewed_by = current_user.id
    activity.review_notes = request.review_notes.strip()
    activity.reviewed_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(activity)
    except Exception:
        db.rollback()
        raise

    return activity
