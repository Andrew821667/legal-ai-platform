"""
Document Processing & Approval Workflow

Добавляет поля для Stage 1: Post-Execution MVP
- processing_pipeline: JSONB - все промежуточные результаты обработки
- approval_status: ENUM - статус утверждения документа
- approved_by, approved_at: tracking информация
- raw_text: полный извлеченный текст документа

Revision ID: 007
Revises: 006
Create Date: 2026-01-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """
    Добавляем поля для document processing pipeline и approval workflow
    """

    # 1. Создаем ENUM для approval_status
    approval_status_enum = postgresql.ENUM(
        'pending', 'approved', 'rejected',
        name='approval_status_enum',
        create_type=True
    )
    approval_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Добавляем поля в contracts_core
    op.add_column('contracts_core',
                  sa.Column('raw_text', sa.Text, nullable=True,
                           comment='Полный извлеченный текст документа'))

    op.add_column('contracts_core',
                  sa.Column('processing_pipeline', postgresql.JSONB, nullable=True,
                           comment='Промежуточные результаты всех этапов обработки'))

    op.add_column('contracts_core',
                  sa.Column('approval_status',
                           postgresql.ENUM('pending', 'approved', 'rejected',
                                         name='approval_status_enum',
                                         create_type=False),
                           nullable=False,
                           server_default='pending',
                           comment='Статус утверждения документа'))

    op.add_column('contracts_core',
                  sa.Column('approved_by', sa.Integer, nullable=True,
                           comment='ID пользователя, утвердившего документ'))

    op.add_column('contracts_core',
                  sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True,
                           comment='Время утверждения документа'))

    op.add_column('contracts_core',
                  sa.Column('rejection_reason', sa.Text, nullable=True,
                           comment='Причина отклонения (если rejected)'))

    # 3. Добавляем индексы для оптимизации запросов
    op.create_index('idx_contracts_approval_status',
                   'contracts_core',
                   ['approval_status'])

    op.create_index('idx_contracts_approved_by',
                   'contracts_core',
                   ['approved_by'])

    # 4. Добавляем поле для хранения метрик обработки
    op.add_column('contracts_core',
                  sa.Column('processing_metrics', postgresql.JSONB, nullable=True,
                           comment='Метрики обработки: время, стоимость, токены'))

    print("✅ Migration 007: Document processing & approval workflow applied")


def downgrade():
    """
    Откат миграции
    """

    # Удаляем индексы
    op.drop_index('idx_contracts_approved_by', table_name='contracts_core')
    op.drop_index('idx_contracts_approval_status', table_name='contracts_core')

    # Удаляем колонки
    op.drop_column('contracts_core', 'processing_metrics')
    op.drop_column('contracts_core', 'rejection_reason')
    op.drop_column('contracts_core', 'approved_at')
    op.drop_column('contracts_core', 'approved_by')
    op.drop_column('contracts_core', 'approval_status')
    op.drop_column('contracts_core', 'processing_pipeline')
    op.drop_column('contracts_core', 'raw_text')

    # Удаляем ENUM тип
    approval_status_enum = postgresql.ENUM(
        'pending', 'approved', 'rejected',
        name='approval_status_enum'
    )
    approval_status_enum.drop(op.get_bind(), checkfirst=True)

    print("✅ Migration 007: Rolled back")
