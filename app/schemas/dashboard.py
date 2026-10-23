from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CurrencyBalance(BaseModel):
    currency: str
    total_balance: Decimal


class RecentTransaction(BaseModel):
    id: int
    wallet_id: int
    transaction_type: str
    amount: Decimal
    currency: str
    status: str
    description: str | None
    created_at: datetime


class DashboardSummary(BaseModel):
    wallet_count: int
    active_wallet_count: int
    balances_by_currency: list[CurrencyBalance]
    total_transactions: int
    completed_transactions: int
    deposits_total: Decimal
    withdrawals_total: Decimal
    transfers_sent_total: Decimal
    open_suspicious_activities: int
    unread_notifications: int


class DashboardTransactions(BaseModel):
    items: list[RecentTransaction]
    limit: int


class DashboardSuspiciousSummary(BaseModel):
    open_count: int
    high_severity_count: int
    recent_items: list[dict]