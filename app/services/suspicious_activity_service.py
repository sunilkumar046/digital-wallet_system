
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.suspicious_activity import SuspiciousActivity
from app.models.transaction import Transaction


class SuspiciousActivityService:
    # Configurable starter thresholds
    LARGE_TRANSACTION_THRESHOLD = Decimal("10000.00")
    HIGH_VALUE_TRANSACTION_THRESHOLD = Decimal("25000.00")

    FREQUENT_TRANSACTION_COUNT = 5
    FREQUENT_TRANSACTION_WINDOW_MINUTES = 5

    @staticmethod
    def _record_flag(
        db: Session,
        transaction: Transaction,
        reason: str,
        severity: str,
        details: str,
    ) -> SuspiciousActivity:
        """
        Avoid creating duplicate flags for the same transaction and reason.
        """

        existing = db.scalar(
            select(SuspiciousActivity).where(
                SuspiciousActivity.transaction_id == transaction.id,
                SuspiciousActivity.reason == reason,
                SuspiciousActivity.status != "RESOLVED",
            )
        )

        if existing is not None:
            return existing

        activity = SuspiciousActivity(
            user_id=transaction.user_id,
            transaction_id=transaction.id,
            reason=reason,
            severity=severity,
            status="OPEN",
            details=details,
        )

        db.add(activity)
        db.flush()

        return activity

    @staticmethod
    def detect_for_transaction(
        db: Session,
        transaction: Transaction,
    ) -> list[SuspiciousActivity]:
        """
        Evaluate one completed transaction against basic rules.

        This method adds flags to the current database transaction.
        The caller is responsible for committing or rolling back.
        """

        if transaction.status != "COMPLETED":
            return []

        flags: list[SuspiciousActivity] = []
        amount = Decimal(str(transaction.amount))

        # Rule 1: Large transaction
        if amount >= SuspiciousActivityService.HIGH_VALUE_TRANSACTION_THRESHOLD:
            flags.append(
                SuspiciousActivityService._record_flag(
                    db=db,
                    transaction=transaction,
                    reason="HIGH_VALUE_TRANSACTION",
                    severity="HIGH",
                    details=(
                        f"Transaction amount {amount} reached or exceeded "
                        f"the high-value threshold of "
                        f"{SuspiciousActivityService.HIGH_VALUE_TRANSACTION_THRESHOLD}."
                    ),
                )
            )

        elif amount >= SuspiciousActivityService.LARGE_TRANSACTION_THRESHOLD:
            flags.append(
                SuspiciousActivityService._record_flag(
                    db=db,
                    transaction=transaction,
                    reason="LARGE_TRANSACTION",
                    severity="MEDIUM",
                    details=(
                        f"Transaction amount {amount} reached or exceeded "
                        f"the large-transaction threshold of "
                        f"{SuspiciousActivityService.LARGE_TRANSACTION_THRESHOLD}."
                    ),
                )
            )

        # Rule 2: Frequent transactions within a short time window
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(
            minutes=SuspiciousActivityService.FREQUENT_TRANSACTION_WINDOW_MINUTES
        )

        recent_count = db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == transaction.user_id,
                Transaction.status == "COMPLETED",
                Transaction.created_at >= window_start,
                Transaction.id != transaction.id,
            )
        ) or 0

        # Include the current transaction in the total.
        if recent_count + 1 >= SuspiciousActivityService.FREQUENT_TRANSACTION_COUNT:
            flags.append(
                SuspiciousActivityService._record_flag(
                    db=db,
                    transaction=transaction,
                    reason="FREQUENT_TRANSACTIONS",
                    severity="MEDIUM",
                    details=(
                        f"At least {recent_count + 1} completed transactions "
                        f"were recorded within approximately "
                        f"{SuspiciousActivityService.FREQUENT_TRANSACTION_WINDOW_MINUTES} minutes."
                    ),
                )
            )

        return flags
