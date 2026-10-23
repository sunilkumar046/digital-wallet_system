from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationReadResponse,
    NotificationResponse,
    UnreadNotificationCount,
)
from app.services.notification_service import NotificationService


router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=list[NotificationResponse],
)
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return NotificationService.list_for_user(
        db=db,
        user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/unread-count",
    response_model=UnreadNotificationCount,
)
def unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "unread_count": NotificationService.unread_count(
            db=db,
            user=current_user,
        )
    }


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return NotificationService.mark_as_read(
        db=db,
        user=current_user,
        notification_id=notification_id,
    )


@router.patch(
    "/read-all",
    response_model=NotificationReadResponse,
)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = NotificationService.mark_all_as_read(
        db=db,
        user=current_user,
    )

    return {
        "success": True,
        "message": f"Marked {count} notification(s) as read.",
    }