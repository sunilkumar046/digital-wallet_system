from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MoneyRequest(BaseModel):
    wallet_id: int = Field(gt=0)
    amount: Decimal = Field(
        gt=Decimal("0"),
        max_digits=18,
        decimal_places=2,
    )
    idempotency_key: str = Field(
        min_length=8,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=255,
    )


class TransferRequest(BaseModel):
    source_wallet_id: int = Field(gt=0)
    destination_wallet_id: int = Field(gt=0)
    amount: Decimal = Field(
        gt=Decimal("0"),
        max_digits=18,
        decimal_places=2,
    )
    idempotency_key: str = Field(
        min_length=8,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=255,
    )


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    related_wallet_id: int | None = None
    user_id: int
    transaction_type: Literal[
        "DEPOSIT",
        "WITHDRAWAL",
        "TRANSFER_OUT",
        "TRANSFER_IN",
    ]
    amount: Decimal
    currency: str
    status: Literal["COMPLETED", "FAILED"]
    idempotency_key: str
    description: str | None
    created_at: datetime