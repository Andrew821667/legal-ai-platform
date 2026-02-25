-- Fix total_cost_usd precision in monthly_api_stats
-- Change from NUMERIC(10,2) to NUMERIC(10,6) to support micro-dollar amounts

-- Alter column type
ALTER TABLE monthly_api_stats
ALTER COLUMN total_cost_usd TYPE NUMERIC(10,6);

-- Update existing data by recalculating from api_usage table
UPDATE monthly_api_stats mas
SET total_cost_usd = (
    SELECT COALESCE(SUM(au.cost_usd), 0)
    FROM api_usage au
    WHERE EXTRACT(YEAR FROM au.date) = mas.year
      AND EXTRACT(MONTH FROM au.date) = mas.month
      AND au.provider = mas.provider
);

-- Verify the update
SELECT
    year,
    month,
    provider,
    total_requests,
    total_tokens,
    total_cost_usd,
    updated_at
FROM monthly_api_stats
WHERE year = 2025 AND month = 12
ORDER BY provider;
