from __future__ import annotations

"""Deferred pgvector migration."""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260225_0002"
down_revision: Union[str, None] = "20260225_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            id UUID PRIMARY KEY,
            namespace VARCHAR(64) NOT NULL,
            source_id VARCHAR(128) NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            metadata JSONB,
            embedding VECTOR(1536) NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_embeddings_hnsw
        ON embeddings USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embeddings_hnsw")
    op.execute("DROP TABLE IF EXISTS embeddings")
