
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.schemas.wallet import (
    WalletCreate,
    WalletResponse,
    WalletUpdate,
)
from app.services.wallet_service import WalletService


router = APIRouter(prefix="/api/wallets", tags=["Wallets"])


@router.post(
    "",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wallet(
    data: WalletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return WalletService.create_wallet(db, current_user, data)


@router.get("", response_model=list[WalletResponse])
def list_wallets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return WalletService.list_wallets(db, current_user)


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return WalletService.get_wallet(db, current_user, wallet_id)


@router.patch("/{wallet_id}", response_model=WalletResponse)
def update_wallet(
    wallet_id: int,
    data: WalletUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return WalletService.update_wallet(
        db, current_user, wallet_id, data
    )


@router.post("/{wallet_id}/freeze", response_model=WalletResponse)
def freeze_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return WalletService.change_status(
        db, current_user, wallet_id, "freeze"
    )


@router.post("/{wallet_id}/unfreeze", response_model=WalletResponse)
def unfreeze_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return WalletService.change_status(
        db, current_user, wallet_id, "unfreeze"
    )
