from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.wallet import WalletCreate, WalletUpdate
from app.services.audit_log_service import AuditLogService


class WalletService:

    @staticmethod
    def create_wallet(
        db: Session,
        user: User,
        data: WalletCreate,
    ) -> Wallet:
        try:
            wallet = Wallet(
                user_id=user.id,
                name=data.name.strip(),
                currency=data.currency,
                available_balance=0,
                pending_balance=0,
                status="ACTIVE",
            )

            db.add(wallet)
            db.flush()

            AuditLogService.record(
                db=db,
                actor=user,
                action="wallet.create",
                resource_type="wallet",
                resource_id=wallet.id,
                details={
                    "name": wallet.name,
                    "currency": wallet.currency,
                    "status": wallet.status,
                },
            )

            db.commit()
            db.refresh(wallet)

            return wallet

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def list_wallets(
        db: Session,
        user: User,
    ) -> list[Wallet]:
        return list(
            db.scalars(
                select(Wallet)
                .where(Wallet.user_id == user.id)
                .order_by(Wallet.created_at.desc())
            ).all()
        )

    @staticmethod
    def get_wallet(
        db: Session,
        user: User,
        wallet_id: int,
    ) -> Wallet:
        wallet = db.scalar(
            select(Wallet).where(
                Wallet.id == wallet_id,
                Wallet.user_id == user.id,
            )
        )

        if wallet is None:
            raise HTTPException(
                status_code=404,
                detail="Wallet not found",
            )

        return wallet

    @staticmethod
    def update_wallet(
        db: Session,
        user: User,
        wallet_id: int,
        data: WalletUpdate,
    ) -> Wallet:
        wallet = WalletService.get_wallet(
            db,
            user,
            wallet_id,
        )

        if wallet.status == "CLOSED":
            raise HTTPException(
                status_code=409,
                detail="Closed wallets cannot be updated",
            )

        try:
            wallet.name = data.name.strip()

            AuditLogService.record(
                db=db,
                actor=user,
                action="wallet.update",
                resource_type="wallet",
                resource_id=wallet.id,
                details={
                    "name": wallet.name,
                },
            )

            db.commit()
            db.refresh(wallet)

            return wallet

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def change_status(
        db: Session,
        user: User,
        wallet_id: int,
        action: str,
    ) -> Wallet:
        wallet = WalletService.get_wallet(
            db,
            user,
            wallet_id,
        )

        if action == "freeze":
            if wallet.status != "ACTIVE":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Cannot freeze wallet in "
                        f"{wallet.status} status"
                    ),
                )

            wallet.status = "FROZEN"

        elif action == "unfreeze":
            if wallet.status != "FROZEN":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Cannot unfreeze wallet in "
                        f"{wallet.status} status"
                    ),
                )

            wallet.status = "ACTIVE"

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported wallet status action",
            )

        try:
            AuditLogService.record(
                db=db,
                actor=user,
                action=f"wallet.{action}",
                resource_type="wallet",
                resource_id=wallet.id,
                details={
                    "new_status": wallet.status,
                },
            )

            db.commit()
            db.refresh(wallet)

            return wallet

        except Exception:
            db.rollback()
            raise