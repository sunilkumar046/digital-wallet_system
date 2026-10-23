
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WalletCreate(BaseModel):
    name: str = Field(default="My Wallet", min_length=1, max_length=100)
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"


class WalletUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    currency: str
    available_balance: Decimal
    pending_balance: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
