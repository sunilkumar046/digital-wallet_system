from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    related_transaction_id: int | None
    created_at: datetime


class UnreadNotificationCount(BaseModel):
    unread_count: int


class NotificationReadResponse(BaseModel):
    success: bool
    message: str