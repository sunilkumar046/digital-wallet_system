from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.suspicious_activity import SuspiciousActivity
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet


class DashboardService:

    @staticmethod
    def summary(db: Session, user: User) -> dict:
        wallet_count = db.scalar(
            select(func.count(Wallet.id)).where(
                Wallet.user_id == user.id
            )
        ) or 0

        active_wallet_count = db.scalar(
            select(func.count(Wallet.id)).where(
                Wallet.user_id == user.id,
                Wallet.status == "ACTIVE",
            )
        ) or 0

        balance_rows = db.execute(
            select(
                Wallet.currency,
                func.sum(Wallet.available_balance),
            )
            .where(Wallet.user_id == user.id)
            .group_by(Wallet.currency)
            .order_by(Wallet.currency)
        ).all()

        balances_by_currency = [
            {
                "currency": currency,
                "total_balance": Decimal(str(total or "0")),
            }
            for currency, total in balance_rows
        ]

        transaction_count = db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == user.id
            )
        ) or 0

        completed_count = db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == user.id,
                Transaction.status == "COMPLETED",
            )
        ) or 0

        def total_for(transaction_types: list[str]) -> Decimal:
            value = db.scalar(
                select(
                    func.coalesce(func.sum(Transaction.amount), 0)
                ).where(
                    Transaction.user_id == user.id,
                    Transaction.status == "COMPLETED",
                    Transaction.transaction_type.in_(transaction_types),
                )
            )
            return Decimal(str(value or "0"))

        open_suspicious = db.scalar(
            select(func.count(SuspiciousActivity.id)).where(
                SuspiciousActivity.user_id == user.id,
                SuspiciousActivity.status == "OPEN",
            )
        ) or 0

        unread_notifications = db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        ) or 0

        return {
            "wallet_count": int(wallet_count),
            "active_wallet_count": int(active_wallet_count),
            "balances_by_currency": balances_by_currency,
            "total_transactions": int(transaction_count),
            "completed_transactions": int(completed_count),
            "deposits_total": total_for(["DEPOSIT"]),
            "withdrawals_total": total_for(["WITHDRAWAL"]),
            "transfers_sent_total": total_for(["TRANSFER_OUT"]),
            "open_suspicious_activities": int(open_suspicious),
            "unread_notifications": int(unread_notifications),
        }

    @staticmethod
    def recent_transactions(
        db: Session,
        user: User,
        limit: int = 10,
    ) -> list[Transaction]:
        rows = db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(
                Transaction.created_at.desc(),
                Transaction.id.desc(),
            )
            .limit(limit)
        ).all()

        return list(rows)

    @staticmethod
    def suspicious_summary(db: Session, user: User) -> dict:
        open_count = db.scalar(
            select(func.count(SuspiciousActivity.id)).where(
                SuspiciousActivity.user_id == user.id,
                SuspiciousActivity.status == "OPEN",
            )
        ) or 0

        high_count = db.scalar(
            select(func.count(SuspiciousActivity.id)).where(
                SuspiciousActivity.user_id == user.id,
                SuspiciousActivity.status == "OPEN",
                SuspiciousActivity.severity.in_(["HIGH", "CRITICAL"]),
            )
        ) or 0

        recent_rows = db.execute(
            select(
                SuspiciousActivity.id,
                SuspiciousActivity.reason,
                SuspiciousActivity.severity,
                SuspiciousActivity.status,
                SuspiciousActivity.transaction_id,
                SuspiciousActivity.detected_at,
            )
            .where(SuspiciousActivity.user_id == user.id)
            .order_by(
                SuspiciousActivity.detected_at.desc(),
                SuspiciousActivity.id.desc(),
            )
            .limit(10)
        ).all()

        return {
            "open_count": int(open_count),
            "high_severity_count": int(high_count),
            "recent_items": [
                {
                    "id": row.id,
                    "reason": row.reason,
                    "severity": row.severity,
                    "status": row.status,
                    "transaction_id": row.transaction_id,
                    "detected_at": row.detected_at,
                }
                for row in recent_rows
            ],
        }