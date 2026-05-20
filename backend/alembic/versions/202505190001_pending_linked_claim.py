"""Link pending submissions to live public claims (additive)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202505190001"
down_revision = "202505180001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pending_claims",
        sa.Column("linked_claim_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_pending_claims_linked_claim_id",
        "pending_claims",
        "claims",
        ["linked_claim_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_pending_claims_linked_claim_id",
        "pending_claims",
        ["linked_claim_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pending_claims_linked_claim_id", table_name="pending_claims")
    op.drop_constraint("fk_pending_claims_linked_claim_id", "pending_claims", type_="foreignkey")
    op.drop_column("pending_claims", "linked_claim_id")
