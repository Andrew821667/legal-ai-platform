"""Create llm_usage_metrics table for tracking model performance and costs

Revision ID: 006_llm_metrics
Revises: 005_knowledge_base
Create Date: 2026-01-09 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_llm_metrics'
down_revision = '005_knowledge_base'
branch_labels = None
depends_on = None


def upgrade():
    """Create llm_usage_metrics table"""

    # ============================================================
    # llm_usage_metrics - Метрики использования LLM моделей
    # ============================================================
    op.create_table(
        'llm_usage_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Документ/сущность
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=True),  # 'contract', 'negotiation', 'amendment'

        # Модель
        sa.Column('model_used', sa.String(50), nullable=False),  # deepseek-v3, claude-4-5-sonnet, gpt-4o, gpt-4o-mini
        sa.Column('model_version', sa.String(50), nullable=True),

        # Оценка сложности
        sa.Column('complexity_score', sa.Numeric(3, 2), nullable=True),  # 0.00 - 1.00
        sa.Column('was_scanned_image', sa.Boolean, nullable=False, server_default='false'),

        # Токены
        sa.Column('tokens_input', sa.Integer, nullable=True),
        sa.Column('tokens_output', sa.Integer, nullable=True),
        sa.Column('tokens_total', sa.Integer, nullable=True),

        # Стоимость
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True),

        # Производительность
        sa.Column('processing_time_sec', sa.Numeric(6, 2), nullable=True),
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True),  # 0.00 - 1.00

        # Результат
        sa.Column('status', sa.String(20), nullable=False),  # 'success', 'partial', 'failed', 'fallback_used'
        sa.Column('error_message', sa.Text, nullable=True),

        # RAG
        sa.Column('rag_used', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('rag_docs_retrieved', sa.Integer, nullable=True),

        # Временные метки
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Constraints
        sa.CheckConstraint('complexity_score BETWEEN 0 AND 1', name='check_complexity_score'),
        sa.CheckConstraint('confidence_score BETWEEN 0 AND 1', name='check_confidence_score'),
        sa.CheckConstraint('tokens_input >= 0', name='check_tokens_input'),
        sa.CheckConstraint('cost_usd >= 0', name='check_cost'),
    )

    # Индексы для llm_usage_metrics
    op.create_index('idx_llm_metrics_document', 'llm_usage_metrics', ['document_id'])
    op.create_index('idx_llm_metrics_model', 'llm_usage_metrics', ['model_used'])
    op.create_index('idx_llm_metrics_created_at', 'llm_usage_metrics', ['created_at'])
    op.create_index('idx_llm_metrics_status', 'llm_usage_metrics', ['status'])
    op.create_index('idx_llm_metrics_entity_type', 'llm_usage_metrics', ['entity_type'])

    print("✅ llm_usage_metrics table created")


def downgrade():
    """Drop llm_usage_metrics table"""
    op.drop_table('llm_usage_metrics')
