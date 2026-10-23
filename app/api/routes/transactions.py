from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.schemas.transaction import (
    MoneyRequest,
    TransferRequest,
    TransactionResponse,
)
from app.services.transaction_service import TransactionService


router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"],
)


@router.post(
    "/deposit",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def deposit(
    request: MoneyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TransactionService.deposit(db, current_user, request)


@router.post(
    "/withdraw",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def withdraw(
    request: MoneyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TransactionService.withdraw(db, current_user, request)


@router.post(
    "/transfer",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def transfer(
    request: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TransactionService.transfer(db, current_user, request)


@router.get(
    "/wallet/{wallet_id}",
    response_model=list[TransactionResponse],
)
def transaction_history(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TransactionService.history(db, current_user, wallet_id)