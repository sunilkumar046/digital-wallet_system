from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User


class NotificationService:

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        related_transaction_id: int | None = None,
    ) -> Notification:
        """
        Add a notification to the current database transaction.
        The caller controls commit and rollback.
        """
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_transaction_id=related_transaction_id,
            is_read=False,
        )

        db.add(notification)
        db.flush()

        return notification

    @staticmethod
    def list_for_user(
        db: Session,
        user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Notification]:
        notifications = db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(
                Notification.created_at.desc(),
                Notification.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()

        return list(notifications)

    @staticmethod
    def unread_count(db: Session, user: User) -> int:
        count = db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )

        return int(count or 0)

    @staticmethod
    def mark_as_read(
        db: Session,
        user: User,
        notification_id: int,
    ) -> Notification:
        notification = db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
            )
        )

        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        if not notification.is_read:
            notification.is_read = True
            db.commit()
            db.refresh(notification)

        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user: User) -> int:
        result = db.execute(
            update(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )

        db.commit()

        return int(result.rowcount or 0)