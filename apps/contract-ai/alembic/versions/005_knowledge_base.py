"""Create knowledge_base table for RAG

Revision ID: 005_knowledge_base
Revises: 004_system_tables
Create Date: 2026-01-09 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_knowledge_base'
down_revision = '004_system_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create knowledge_base table for RAG"""

    # ============================================================
    # knowledge_base - База знаний для RAG
    # ============================================================
    op.create_table(
        'knowledge_base',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Тип контента
        sa.Column('content_type', sa.String(50), nullable=False),

        # Контент
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),

        # Эмбеддинг для векторного поиска
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),

        # Метаданные
        sa.Column('metadata', postgresql.JSONB, nullable=True),

        # Источник
        sa.Column('source', sa.String(255), nullable=True),  # URL, file path, manual entry
        sa.Column('source_type', sa.String(50), nullable=True),  # 'document', 'regulation', 'case_law'

        # Приоритет и активность
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),

        # Статистика использования
        sa.Column('usage_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime, nullable=True),

        # Временные метки
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('created_by', sa.String(36), nullable=True),

        # Constraints
        sa.CheckConstraint(
            "content_type IN ('best_practice', 'regulation', 'precedent', 'template_clause', 'risk_pattern', 'negotiation_tactic')",
            name='check_knowledge_content_type'
        ),
    )

    # Индексы для knowledge_base
    op.create_index('idx_knowledge_content_type', 'knowledge_base', ['content_type'])
    op.create_index('idx_knowledge_active', 'knowledge_base', ['is_active'])
    op.create_index('idx_knowledge_priority', 'knowledge_base', ['priority'])
    op.create_index('idx_knowledge_metadata', 'knowledge_base', ['metadata'],
                    postgresql_using='gin')

    # Vector index for similarity search
    op.execute("""
        CREATE INDEX idx_knowledge_embedding
        ON knowledge_base
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # ============================================================
    # Вставить примеры best practices
    # ============================================================
    op.execute("""
        INSERT INTO knowledge_base (content_type, title, content, metadata, source_type, priority)
        VALUES
            (
                'best_practice',
                'Ограничение ответственности в договорах поставки',
                'В договорах поставки рекомендуется ограничивать ответственность суммой договора. '
                'Неограниченная ответственность создает критический финансовый риск.',
                '{"category": "liability", "applies_to": ["supply", "services"]}',
                'regulation',
                10
            ),
            (
                'risk_pattern',
                'Иностранная подсудность',
                'Условие о рассмотрении споров в иностранных судах создает критический риск: '
                'высокие издержки, сложность исполнения решений, незнакомая правовая система.',
                '{"category": "dispute_resolution", "risk_level": "critical"}',
                'case_law',
                10
            ),
            (
                'negotiation_tactic',
                'Компромисс по условиям предоплаты',
                'Если контрагент настаивает на предоплате >50%, предложите компромисс: '
                '30% предоплата + банковская гарантия или поэтапная оплата с milestone.',
                '{"category": "payment_terms", "success_rate": 0.75}',
                'document',
                8
            ),
            (
                'template_clause',
                'Стандартная формулировка штрафа за просрочку',
                'За нарушение сроков поставки Поставщик уплачивает Покупателю неустойку '
                'в размере 0,1% от стоимости непоставленного товара за каждый день просрочки, '
                'но не более 10% от общей стоимости договора.',
                '{"category": "penalty", "max_cap": 0.1, "daily_rate": 0.001}',
                'document',
                9
            )
    """)

    print("✅ knowledge_base table created")
    print("✅ Sample best practices inserted")


def downgrade():
    """Drop knowledge_base table"""
    op.drop_table('knowledge_base')
