from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_transactions_amount_positive",
        ),
        CheckConstraint(
            "transaction_type IN "
            "('DEPOSIT', 'WITHDRAWAL', 'TRANSFER_OUT', 'TRANSFER_IN')",
            name="ck_transactions_type_valid",
        ),
        CheckConstraint(
            "status IN ('COMPLETED', 'FAILED')",
            name="ck_transactions_status_valid",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_transactions_user_idempotency",
        ),
        Index(
            "ix_transactions_wallet_created",
            "wallet_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


    related_wallet_id: Mapped[int | None] = mapped_column(
    ForeignKey("wallets.id", ondelete="RESTRICT"),
    nullable=True,
    index=True,
     )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="COMPLETED",
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    wallet = relationship(
        "Wallet",
        back_populates="transactions",
        foreign_keys=[wallet_id],
    )

    related_wallet = relationship(
        "Wallet",
        foreign_keys=[related_wallet_id],
    )

    user = relationship("User")