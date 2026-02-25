"""Create system_config and user_approvals tables

Revision ID: 004_system_tables
Revises: 003_negotiation_tables
Create Date: 2026-01-09 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_system_tables'
down_revision = '003_negotiation_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create system_config and user_approvals tables"""

    # ============================================================
    # 1. system_config - Конфигурация системы
    # ============================================================
    op.create_table(
        'system_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Ключ конфигурации
        sa.Column('config_key', sa.String(100), nullable=False, unique=True),

        # Значение (JSONB для гибкости)
        sa.Column('config_value', postgresql.JSONB, nullable=False),

        # Описание
        sa.Column('description', sa.Text, nullable=True),

        # Категория
        sa.Column('category', sa.String(50), nullable=True),  # 'system_mode', 'modules', 'llm', 'rag'

        # Временные метки
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_by', sa.String(36), nullable=True),
    )

    # Индексы для system_config
    op.create_index('idx_system_config_key', 'system_config', ['config_key'], unique=True)
    op.create_index('idx_system_config_category', 'system_config', ['category'])

    # Вставить дефолтные значения
    op.execute("""
        INSERT INTO system_config (config_key, config_value, description, category)
        VALUES
            ('system_mode', '{"mode": "full_load"}', 'Режим работы системы: full_load, sequential, manual', 'system_mode'),
            ('enabled_modules', '{"modules": ["ocr", "level1_extraction", "llm_extraction", "rag_filter", "validation"]}', 'Включенные модули (для ручного режима)', 'modules'),
            ('rag_enabled', '{"enabled": true, "top_k": 5, "similarity_threshold": 0.7}', 'Настройки RAG', 'rag'),
            ('router_config', '{"default_model": "deepseek-v3", "complexity_threshold": 0.8}', 'Настройки Smart Router', 'llm')
    """)

    # ============================================================
    # 2. user_approvals - Отслеживание одобрений
    # ============================================================
    op.create_table(
        'user_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Тип сущности, требующей одобрения
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Действие
        sa.Column('action', sa.String(100), nullable=False),

        # Статус
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),

        # Превью данных для одобрения
        sa.Column('data_preview', postgresql.JSONB, nullable=True),

        # Одобрение
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('comment', sa.Text, nullable=True),

        # Временные метки
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Constraints
        sa.CheckConstraint(
            "entity_type IN ('negotiation', 'extraction', 'protocol', 'digitization', 'amendment')",
            name='check_approval_entity_type'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name='check_approval_status'
        ),
        sa.CheckConstraint(
            "action IN ('approve_protocol', 'reject_extraction', 'approve_digitization', "
            "'approve_negotiation', 'approve_amendment', 'reject_protocol')",
            name='check_approval_action'
        ),
    )

    # Индексы для user_approvals
    op.create_index('idx_user_approvals_entity', 'user_approvals', ['entity_type', 'entity_id'])
    op.create_index('idx_user_approvals_status', 'user_approvals', ['status'])
    op.create_index('idx_user_approvals_created_at', 'user_approvals', ['created_at'])
    op.create_index('idx_user_approvals_approved_by', 'user_approvals', ['approved_by'])

    print("✅ system_config table created with default values")
    print("✅ user_approvals table created")


def downgrade():
    """Drop system tables"""
    op.drop_table('user_approvals')
    op.drop_table('system_config')
