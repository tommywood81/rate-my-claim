"""Allow pending claims without a registered submitter."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202505170001"
down_revision: Union[str, None] = "202505160001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nullable submitted_by for guest submissions."""
    op.alter_column(
        "pending_claims",
        "submitted_by",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.drop_constraint("pending_claims_submitted_by_fkey", "pending_claims", type_="foreignkey")
    op.create_foreign_key(
        "pending_claims_submitted_by_fkey",
        "pending_claims",
        "users",
        ["submitted_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Require submitted_by again (fails if NULL rows exist)."""
    op.drop_constraint("pending_claims_submitted_by_fkey", "pending_claims", type_="foreignkey")
    op.create_foreign_key(
        "pending_claims_submitted_by_fkey",
        "pending_claims",
        "users",
        ["submitted_by"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "pending_claims",
        "submitted_by",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
