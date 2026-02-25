"""Add pgvector extension and embedding column

Revision ID: 002_pgvector
Revises: 001_idp_tables
Create Date: 2026-01-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_pgvector'
down_revision = '001_idp_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Enable pgvector extension and add embedding column"""

    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Add embedding column to contracts_core
    op.add_column('contracts_core',
                  sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True))

    # Create index for vector similarity search
    op.execute("""
        CREATE INDEX idx_contracts_core_embedding
        ON contracts_core
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    print("✅ pgvector extension enabled")
    print("✅ embedding column added to contracts_core")


def downgrade():
    """Remove pgvector extension and embedding column"""

    # Drop index
    op.drop_index('idx_contracts_core_embedding', table_name='contracts_core')

    # Drop column
    op.drop_column('contracts_core', 'embedding')

    # Drop extension
    op.execute('DROP EXTENSION IF EXISTS vector')
