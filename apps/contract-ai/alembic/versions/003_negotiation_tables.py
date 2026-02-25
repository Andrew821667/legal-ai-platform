"""Create negotiation_sessions and disagreements tables for Pre-Execution

Revision ID: 003_negotiation_tables
Revises: 002_pgvector
Create Date: 2026-01-09 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_negotiation_tables'
down_revision = '002_pgvector'
branch_labels = None
depends_on = None


def upgrade():
    """Create negotiation_sessions and disagreements tables"""

    # ============================================================
    # 1. negotiation_sessions - Сессии анализа черновиков
    # ============================================================
    op.create_table(
        'negotiation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Загруженный документ
        sa.Column('uploaded_doc_path', sa.Text, nullable=False),
        sa.Column('doc_hash', sa.String(64), nullable=True),  # SHA-256 hash для дедупликации

        # Статус сессии
        sa.Column('status', sa.String(20), nullable=False, server_default='analyzing'),

        # Ссылка на шаблон для сравнения
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Результаты анализа
        sa.Column('risk_score', sa.Numeric(3, 2), nullable=True),  # 0.00 - 1.00
        sa.Column('ai_recommendations', postgresql.JSONB, nullable=True),  # Рекомендации системы

        # Метаданные обработки
        sa.Column('processed_by_model', sa.String(50), nullable=True),  # deepseek-v3, claude-4-5-sonnet
        sa.Column('processing_time_ms', sa.Integer, nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True),

        # Временные метки
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime, nullable=True),

        # Пользователь
        sa.Column('created_by', sa.String(36), nullable=True),

        # Constraints
        sa.CheckConstraint(
            "status IN ('analyzing', 'awaiting_approval', 'approved', 'rejected', 'archived')",
            name='check_negotiation_status'
        ),
        sa.CheckConstraint('risk_score BETWEEN 0 AND 1', name='check_risk_score'),
    )

    # Индексы для negotiation_sessions
    op.create_index('idx_negotiation_status', 'negotiation_sessions', ['status'])
    op.create_index('idx_negotiation_created_at', 'negotiation_sessions', ['created_at'])
    op.create_index('idx_negotiation_template', 'negotiation_sessions', ['template_id'])
    op.create_index('idx_negotiation_doc_hash', 'negotiation_sessions', ['doc_hash'])
    op.create_index('idx_negotiation_recommendations', 'negotiation_sessions', ['ai_recommendations'],
                    postgresql_using='gin')

    # ============================================================
    # 2. disagreements - Протокол разногласий
    # ============================================================
    op.create_table(
        'disagreements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Ссылка на сессию
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Расположение в документе
        sa.Column('section', sa.String(100), nullable=True),  # "5. Ответственность сторон"
        sa.Column('clause_number', sa.String(20), nullable=True),  # "5.1"

        # Формулировки
        sa.Column('their_clause', sa.Text, nullable=False),  # Что предлагает контрагент
        sa.Column('our_standard', sa.Text, nullable=True),   # Наш стандарт
        sa.Column('suggested_wording', sa.Text, nullable=True),  # Предложение для компромисса

        # Оценка риска
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('risk_explanation', sa.Text, nullable=True),

        # AI рекомендация (НОВОЕ в v2.1)
        sa.Column('ai_recommendation', sa.Text, nullable=True),
        sa.Column('precedents', postgresql.JSONB, nullable=True),  # Похожие прецеденты из RAG
        sa.Column('suggested_actions', postgresql.JSONB, nullable=True),  # ["Настаивать", "Компромисс", ...]

        # Одобрение пользователем (НОВОЕ в v2.1)
        sa.Column('user_approved', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('user_comment', sa.Text, nullable=True),

        # Временные метки
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Foreign keys
        sa.ForeignKeyConstraint(['session_id'], ['negotiation_sessions.id'],
                                ondelete='CASCADE'),

        # Constraints
        sa.CheckConstraint(
            "risk_level IN ('critical', 'high', 'medium', 'low')",
            name='check_disagreement_risk_level'
        ),
    )

    # Индексы для disagreements
    op.create_index('idx_disagreements_session', 'disagreements', ['session_id'])
    op.create_index('idx_disagreements_risk_level', 'disagreements', ['risk_level'])
    op.create_index('idx_disagreements_approved', 'disagreements', ['user_approved'])
    op.create_index('idx_disagreements_precedents', 'disagreements', ['precedents'],
                    postgresql_using='gin')

    print("✅ negotiation_sessions table created")
    print("✅ disagreements table created")


def downgrade():
    """Drop negotiation tables"""
    op.drop_table('disagreements')
    op.drop_table('negotiation_sessions')
