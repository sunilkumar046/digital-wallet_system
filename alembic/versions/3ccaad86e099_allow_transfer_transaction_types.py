"""Allow transfer transaction types.

Revision ID: 3ccaad86e099
Revises: 2a26ce010b09
Create Date: 2026-10-16 08:26:52.055457
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3ccaad86e099"
down_revision: Union[str, Sequence[str], None] = "2a26ce010b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow all supported transaction types."""

    op.drop_constraint(
        "ck_transactions_type_valid",
        "transactions",
        type_="check",
    )

    op.create_check_constraint(
        "ck_transactions_type_valid",
        "transactions",
        "transaction_type IN "
        "('DEPOSIT', 'WITHDRAWAL', 'TRANSFER_OUT', 'TRANSFER_IN')",
    )


def downgrade() -> None:
    """Restore the original transaction type constraint."""

    op.drop_constraint(
        "ck_transactions_type_valid",
        "transactions",
        type_="check",
    )

    op.create_check_constraint(
        "ck_transactions_type_valid",
        "transactions",
        "transaction_type IN ('DEPOSIT', 'WITHDRAWAL')",
    )
