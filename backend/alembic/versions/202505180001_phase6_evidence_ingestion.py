"""Phase 6: evidence artifacts, chunks, source feeds, ingestion job extensions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "202505180001"
down_revision: Union[str, None] = "202505170001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add evidence ingestion tables and extend ingestion_jobs."""
    op.create_table(
        "evidence_source_feeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("feed_url", sa.String(2048), nullable=False),
        sa.Column("feed_type", sa.String(32), nullable=False, server_default="rss"),
        sa.Column("publisher_name", sa.String(255), nullable=True),
        sa.Column("credibility_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("feed_url", name="uq_evidence_source_feeds_url"),
    )

    op.create_table(
        "evidence_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("authors", sa.String(512), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("cleaned_content", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("retrieval_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieval_source", sa.String(120), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(120), nullable=True),
        sa.Column("embedding_version", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("url", name="uq_evidence_artifacts_url"),
    )
    op.create_index("ix_evidence_artifacts_content_hash", "evidence_artifacts", ["content_hash"])

    op.create_table(
        "evidence_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence_artifacts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(120), nullable=True),
        sa.Column("embedding_version", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_evidence_chunks_artifact", "evidence_chunks", ["artifact_id"])
    op.create_index("ix_evidence_chunks_evidence", "evidence_chunks", ["evidence_id"])

    op.add_column("ingestion_jobs", sa.Column("source_type", sa.String(40), server_default="manual_url", nullable=False))
    op.add_column(
        "ingestion_jobs",
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence_source_feeds.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence_artifacts.id", ondelete="SET NULL"), nullable=True),
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_evidence_chunks_embedding_hnsw
        ON evidence_chunks USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_evidence_artifacts_embedding_hnsw
        ON evidence_artifacts USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop Phase 6 evidence ingestion tables."""
    op.execute("DROP INDEX IF EXISTS ix_evidence_artifacts_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_embedding_hnsw")
    op.drop_column("ingestion_jobs", "artifact_id")
    op.drop_column("ingestion_jobs", "feed_id")
    op.drop_column("ingestion_jobs", "source_type")
    op.drop_table("evidence_chunks")
    op.drop_index("ix_evidence_artifacts_content_hash", table_name="evidence_artifacts")
    op.drop_table("evidence_artifacts")
    op.drop_table("evidence_source_feeds")
