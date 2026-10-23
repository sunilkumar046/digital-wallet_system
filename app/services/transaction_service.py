
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.transaction import MoneyRequest, TransferRequest
from app.services.audit_log_service import AuditLogService
from app.services.notification_service import NotificationService
from app.services.suspicious_activity_service import SuspiciousActivityService


logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


class TransactionService:
    """Business logic for wallet deposits, withdrawals and transfers."""

    # ---------------------------------------------------------
    # Common helpers
    # ---------------------------------------------------------

    @staticmethod
    def _money(value) -> Decimal:
        return Decimal(str(value)).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _get_idempotency_key(request) -> str:
        key = getattr(request, "idempotency_key", None)

        if not key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An idempotency key is required.",
            )

        return str(key)

    @staticmethod
    def _existing_transaction(
        db: Session,
        user_id: int,
        key: str,
    ):
        return (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                Transaction.idempotency_key == key,
            )
            .first()
        )

    @staticmethod
    def _validate_existing(
        existing: Transaction,
        transaction_type: str,
        amount: Decimal,
        wallet_id: int,
        related_wallet_id: int | None = None,
    ):
        existing_type = str(
            getattr(existing.transaction_type, "value",
                    existing.transaction_type)
        ).upper()

        same_request = (
            existing_type == transaction_type.upper()
            and TransactionService._money(existing.amount)
            == TransactionService._money(amount)
            and existing.wallet_id == wallet_id
        )

        if related_wallet_id is not None:
            same_request = (
                same_request
                and existing.related_wallet_id == related_wallet_id
            )

        if not same_request:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This idempotency key has already been used "
                    "for a different transaction."
                ),
            )

        return existing

    @staticmethod
    def _validate_amount(amount: Decimal):
        amount = TransactionService._money(amount)

        if amount <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be greater than zero.",
            )

        return amount

    @staticmethod
    def _validate_wallet_active(wallet: Wallet):
        wallet_status = getattr(wallet.status, "value", wallet.status)
        wallet_status = str(wallet_status).upper()

        if wallet_status in {"INACTIVE", "BLOCKED", "CLOSED", "FROZEN"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Wallet is not active. Current status: {wallet_status}.",
            )

        if hasattr(wallet, "is_active") and not wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wallet is not active.",
            )

    @staticmethod
    def _validate_wallet_owner(wallet: Wallet, user: User):
        if wallet.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to use this wallet.",
            )

    @staticmethod
    def _get_locked_wallet(db: Session, wallet_id: int) -> Wallet:
        wallet = db.execute(
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        ).scalar_one_or_none()

        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found.",
            )

        return wallet

    @staticmethod
    def _get_user(db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    # ---------------------------------------------------------
    # Transaction limits
    # ---------------------------------------------------------

    @staticmethod
    def _enforce_transaction_limits(
        db: Session,
        user_id: int,
        transaction_type: str,
        amount: Decimal,
    ):
        amount = TransactionService._money(amount)
        transaction_type = transaction_type.upper()

        limits = {
            "DEPOSIT": settings.MAX_SINGLE_DEPOSIT,
            "WITHDRAWAL": settings.MAX_SINGLE_WITHDRAWAL,
            "TRANSFER_OUT": settings.MAX_SINGLE_TRANSFER,
        }

        limit = limits.get(transaction_type)

        if limit is not None and amount > TransactionService._money(limit):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{transaction_type} exceeds the single-transaction "
                    f"limit of {TransactionService._money(limit)}."
                ),
            )

        # Deposits do not count toward the daily outgoing limit.
        if transaction_type not in {"WITHDRAWAL", "TRANSFER_OUT"}:
            return

        now = datetime.now(timezone.utc)
        start_of_day = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        outgoing_types = ["WITHDRAWAL", "TRANSFER_OUT"]

        daily_total = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                func.upper(Transaction.transaction_type).in_(outgoing_types),
                Transaction.status == "COMPLETED",
                Transaction.created_at >= start_of_day,
            )
            .scalar()
        )

        daily_total = TransactionService._money(daily_total or 0)
        daily_limit = TransactionService._money(
            settings.DAILY_OUTGOING_LIMIT
        )

        if daily_total + amount > daily_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Daily outgoing transaction limit exceeded. "
                    f"Daily limit: {daily_limit}; "
                    f"already used: {daily_total}."
                ),
            )

    # ---------------------------------------------------------
    # Audit, notification and suspicious activity
    # ---------------------------------------------------------

    @staticmethod
    def _record_audit(
        db: Session,
        user: User,
        transaction: Transaction,
        action: str,
        details: dict | None = None,
    ):
        AuditLogService.record(
            db=db,
            actor=user,
            action=action,
            resource_type="transaction",
            resource_id=transaction.id,
            details=details or {},
        )

    @staticmethod
    def _create_notification(
        db: Session,
        user_id: int,
        transaction: Transaction,
        title: str,
        message: str,
    ):
        NotificationService.create(
            db=db,
            user_id=user_id,
            title=title,
            message=message,
            notification_type="TRANSACTION",
            related_transaction_id=transaction.id,
        )

    @staticmethod
    def _check_suspicious_activity(
        db: Session,
        transaction: Transaction,
    ):
        return SuspiciousActivityService.detect_for_transaction(
            db=db,
            transaction=transaction,
        )

    # ---------------------------------------------------------
    # Deposit and withdrawal processing
    # ---------------------------------------------------------

    @staticmethod
    def _process(
        db: Session,
        user: User,
        request: MoneyRequest,
        transaction_type: str,
    ):
        transaction_type = transaction_type.upper()
        amount = TransactionService._validate_amount(request.amount)
        key = TransactionService._get_idempotency_key(request)

        try:
            # Return the original result if this request was already processed.
            existing = TransactionService._existing_transaction(
                db=db,
                user_id=user.id,
                key=key,
            )

            if existing:
                return TransactionService._validate_existing(
                    existing=existing,
                    transaction_type=transaction_type,
                    amount=amount,
                    wallet_id=request.wallet_id,
                )

            wallet = TransactionService._get_locked_wallet(
                db=db,
                wallet_id=request.wallet_id,
            )

            TransactionService._validate_wallet_owner(wallet, user)
            TransactionService._validate_wallet_active(wallet)

            TransactionService._enforce_transaction_limits(
                db=db,
                user_id=user.id,
                transaction_type=transaction_type,
                amount=amount,
            )

            available_balance = TransactionService._money(
                wallet.available_balance
            )

            if (
                transaction_type == "WITHDRAWAL"
                and available_balance < amount
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient wallet balance.",
                )

            # Update the actual balance field from the Wallet model.
            if transaction_type == "DEPOSIT":
                wallet.available_balance = available_balance + amount
            else:
                wallet.available_balance = available_balance - amount

            transaction = Transaction(
                user_id=user.id,
                wallet_id=wallet.id,
                related_wallet_id=None,
                transaction_type=transaction_type,
                amount=amount,
                currency=wallet.currency,
                status="COMPLETED",
                idempotency_key=key,
                description=request.description,
            )

            db.add(transaction)
            db.flush()

            TransactionService._check_suspicious_activity(
                db=db,
                transaction=transaction,
            )

            TransactionService._record_audit(
                db=db,
                user=user,
                transaction=transaction,
                action=f"TRANSACTION_{transaction_type}",
                details={
                    "wallet_id": wallet.id,
                    "amount": str(amount),
                    "currency": wallet.currency,
                    "transaction_type": transaction_type,
                },
            )

            TransactionService._create_notification(
                db=db,
                user_id=user.id,
                transaction=transaction,
                title=f"Wallet {transaction_type.lower()} successful",
                message=(
                    f"Your {transaction_type.lower()} of "
                    f"{amount} {wallet.currency} was successful."
                ),
            )

            db.commit()
            db.refresh(transaction)

            return transaction

        except HTTPException:
            db.rollback()
            raise

        except IntegrityError as exc:
            db.rollback()

            # Handle two concurrent requests using the same idempotency key.
            existing = TransactionService._existing_transaction(
                db=db,
                user_id=user.id,
                key=key,
            )

            if existing:
                return TransactionService._validate_existing(
                    existing=existing,
                    transaction_type=transaction_type,
                    amount=amount,
                    wallet_id=request.wallet_id,
                )

            logger.exception("Database integrity error processing transaction")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction could not be processed because of a conflict.",
            ) from exc

        except Exception as exc:
            db.rollback()
            logger.exception("Unexpected error processing transaction")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing the transaction.",
            ) from exc

    @staticmethod
    def deposit(db: Session, user: User, request: MoneyRequest):
        return TransactionService._process(
            db=db,
            user=user,
            request=request,
            transaction_type="DEPOSIT",
        )

    @staticmethod
    def withdraw(db: Session, user: User, request: MoneyRequest):
        return TransactionService._process(
            db=db,
            user=user,
            request=request,
            transaction_type="WITHDRAWAL",
        )

    # ---------------------------------------------------------
    # Transfers
    # ---------------------------------------------------------

    @staticmethod
    def transfer(
        db: Session,
        user: User,
        request: TransferRequest,
    ):
        amount = TransactionService._validate_amount(request.amount)
        key = TransactionService._get_idempotency_key(request)

        if request.source_wallet_id == request.destination_wallet_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source and destination wallets must be different.",
            )

        try:
            existing = TransactionService._existing_transaction(
                db=db,
                user_id=user.id,
                key=key,
            )

            if existing:
                return TransactionService._validate_existing(
                    existing=existing,
                    transaction_type="TRANSFER_OUT",
                    amount=amount,
                    wallet_id=request.source_wallet_id,
                    related_wallet_id=request.destination_wallet_id,
                )

            # Lock in consistent ID order to reduce deadlock risk.
            wallet_ids = sorted(
                [
                    request.source_wallet_id,
                    request.destination_wallet_id,
                ]
            )

            locked_wallets = {}

            for wallet_id in wallet_ids:
                locked_wallets[wallet_id] = (
                    TransactionService._get_locked_wallet(
                        db=db,
                        wallet_id=wallet_id,
                    )
                )

            source_wallet = locked_wallets[request.source_wallet_id]
            destination_wallet = locked_wallets[
                request.destination_wallet_id
            ]

            TransactionService._validate_wallet_owner(source_wallet, user)
            TransactionService._validate_wallet_active(source_wallet)
            TransactionService._validate_wallet_active(destination_wallet)

            if source_wallet.currency != destination_wallet.currency:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot transfer between wallets with different currencies.",
                )

            TransactionService._enforce_transaction_limits(
                db=db,
                user_id=user.id,
                transaction_type="TRANSFER_OUT",
                amount=amount,
            )

            source_balance = TransactionService._money(
                source_wallet.available_balance
            )

            if source_balance < amount:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient wallet balance for transfer.",
                )

            recipient = TransactionService._get_user(
                db=db,
                user_id=destination_wallet.user_id,
            )

            # Update both wallets within the same database transaction.
            source_wallet.available_balance = source_balance - amount

            destination_wallet.available_balance = (
                TransactionService._money(
                    destination_wallet.available_balance
                ) + amount
            )

            outgoing = Transaction(
                user_id=user.id,
                wallet_id=source_wallet.id,
                related_wallet_id=destination_wallet.id,
                transaction_type="TRANSFER_OUT",
                amount=amount,
                currency=source_wallet.currency,
                status="COMPLETED",
                idempotency_key=key,
                description=request.description,
            )

            # The incoming ledger entry needs its own unique key.
            incoming_key = f"{key[:65]}:in:{uuid4().hex}"

            incoming = Transaction(
                user_id=recipient.id,
                wallet_id=destination_wallet.id,
                related_wallet_id=source_wallet.id,
                transaction_type="TRANSFER_IN",
                amount=amount,
                currency=destination_wallet.currency,
                status="COMPLETED",
                idempotency_key=incoming_key,
                description=request.description,
            )

            db.add_all([outgoing, incoming])
            db.flush()

            TransactionService._check_suspicious_activity(
                db=db,
                transaction=outgoing,
            )

            TransactionService._record_audit(
                db=db,
                user=user,
                transaction=outgoing,
                action="TRANSACTION_TRANSFER",
                details={
                    "source_wallet_id": source_wallet.id,
                    "destination_wallet_id": destination_wallet.id,
                    "amount": str(amount),
                    "currency": source_wallet.currency,
                },
            )

            TransactionService._create_notification(
                db=db,
                user_id=user.id,
                transaction=outgoing,
                title="Transfer sent",
                message=(
                    f"You transferred {amount} "
                    f"{source_wallet.currency} successfully."
                ),
            )

            TransactionService._create_notification(
                db=db,
                user_id=recipient.id,
                transaction=incoming,
                title="Transfer received",
                message=(
                    f"You received {amount} "
                    f"{destination_wallet.currency}."
                ),
            )

            db.commit()
            db.refresh(outgoing)

            return outgoing

        except HTTPException:
            db.rollback()
            raise

        except IntegrityError as exc:
            db.rollback()

            existing = TransactionService._existing_transaction(
                db=db,
                user_id=user.id,
                key=key,
            )

            if existing:
                return TransactionService._validate_existing(
                    existing=existing,
                    transaction_type="TRANSFER_OUT",
                    amount=amount,
                    wallet_id=request.source_wallet_id,
                    related_wallet_id=request.destination_wallet_id,
                )

            logger.exception("Database integrity error processing transfer")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transfer could not be processed because of a conflict.",
            ) from exc

        except Exception as exc:
            db.rollback()
            logger.exception("Unexpected error processing transfer")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing the transfer.",
            ) from exc

    # ---------------------------------------------------------
    # Transaction history
    # ---------------------------------------------------------

    @staticmethod
    def history(
        db: Session,
        user: User,
        wallet_id: int | None = None,
    ):
        query = db.query(Transaction).filter(
            Transaction.user_id == user.id
        )

        if wallet_id is not None:
            # Ensure the requested wallet belongs to the authenticated user.
            wallet = db.query(Wallet).filter(
                Wallet.id == wallet_id
            ).first()

            if wallet is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wallet not found.",
                )

            TransactionService._validate_wallet_owner(wallet, user)

            query = query.filter(Transaction.wallet_id == wallet_id)

        return query.order_by(Transaction.created_at.desc()).all()
