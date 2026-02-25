-- Добавление российских новостных RSS источников
-- Выполнить: docker compose exec -T postgres psql -U legal_user -d legal_ai_news -f /path/to/this/file.sql

-- Удаляем старые записи если есть (idempotent)
DELETE FROM sources WHERE name IN (
    'Lenta.ru - Технологии',
    'RBC - Технологии',
    'Interfax - Наука и технологии',
    'TASS - Наука и технологии',
    'Habr - Новости'
);

-- Добавляем российские источники
INSERT INTO sources (name, url, type, enabled, quality_score)
VALUES
    -- Lenta.ru
    ('Lenta.ru - Технологии', 'https://lenta.ru/rss/news/technology', 'rss', true, 0.7),

    -- RBC
    ('RBC - Технологии', 'https://rssexport.rbc.ru/rbcnews/news/20/full.rss', 'rss', true, 0.8),

    -- Interfax
    ('Interfax - Наука и технологии', 'https://www.interfax.ru/rss.asp', 'rss', true, 0.75),

    -- TASS
    ('TASS - Наука и технологии', 'https://tass.ru/rss/v2.xml', 'rss', true, 0.75),

    -- Habr
    ('Habr - Новости', 'https://habr.com/ru/rss/news/?fl=ru', 'rss', true, 0.6)

ON CONFLICT (name) DO UPDATE SET
    url = EXCLUDED.url,
    type = EXCLUDED.type,
    enabled = EXCLUDED.enabled,
    quality_score = EXCLUDED.quality_score;

-- Проверяем результат
SELECT id, name, url, type, enabled, quality_score FROM sources ORDER BY quality_score DESC;
