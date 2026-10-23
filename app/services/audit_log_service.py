from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


class AuditLogService:
    @staticmethod
    def record(
        db: Session,
        actor: User | None,
        action: str,
        resource_type: str,
        resource_id: int | str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Add an audit record to the current database transaction.

        This method intentionally does not commit. The caller commits
        the audit record together with the business operation.
        """
        entry = AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=(
                str(resource_id) if resource_id is not None else None
            ),
            details=details,
            ip_address=ip_address,
        )

        db.add(entry)
        return entry