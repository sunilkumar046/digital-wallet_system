from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.database.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse


router = APIRouter(
    prefix="/api/audit-logs",
    tags=["Audit Logs"],
)

AUDIT_VIEW_ROLES = ("Super Admin", "Admin")


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*AUDIT_VIEW_ROLES)
    ),
):
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)

    if resource_type:
        query = query.where(
            AuditLog.resource_type == resource_type
        )

    if actor_user_id is not None:
        query = query.where(
            AuditLog.actor_user_id == actor_user_id
        )

    query = (
        query
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(query).all())


@router.get(
    "/{audit_id}",
    response_model=AuditLogResponse,
)
def get_audit_log(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(*AUDIT_VIEW_ROLES)
    ),
):
    entry = db.get(AuditLog, audit_id)

    if entry is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Audit log entry not found.",
        )

    return entry