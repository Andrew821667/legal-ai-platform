# Phase 1 Release Gate (backend core)

Дата фиксации: 2026-03-06

## Проверки
- [x] `core-api` тесты:
  - Команда: `.venv/bin/pytest apps/core-api/tests -q`
  - Результат: `22 passed`
- [x] Интеграционный smoke:
  - Команда: `set -a && source .env && set +a && bash infra/scripts/integration_test.sh`
  - Результат: `Integration test passed`
- [x] Health endpoints:
  - `GET /health` -> `200`
  - `GET /health/detailed` -> `200`

## Важно по контрактной части
- На текущем этапе production-контур договоров = `core-api contract_jobs` + `apps/contract-worker`.
- `apps/contract-ai` не интегрирован в runtime-контур и не деплоится через основной compose.
