# Docs Index

Обновлено: 2026-03-12

## Source of truth

Для текущего состояния проекта source of truth считаются:
- [project-control-checklist.md](./project-control-checklist.md) — текущий статус проекта и остаток работ;
- [architecture.md](./architecture.md) — актуальная runtime-архитектура и ключевые API;
- [runbook.md](./runbook.md) — эксплуатация, деплой и smoke-порядок;
- [contract-ai-boundary.md](./contract-ai-boundary.md) — граница ответственности между платформой и внешним `Contract_AI_System`;
- [contract-ai-entrypoints.md](./contract-ai-entrypoints.md) — канонические точки входа в внешний модуль;
- [product-offer-sync-checklist.md](./product-offer-sync-checklist.md) — актуальная продуктовая модель и offer sync;
- [special-paid-consultation-placement.md](./special-paid-consultation-placement.md) — правила показа special paid consultation;
- [compliance-operating-model-review-2026-03-11.md](./compliance-operating-model-review-2026-03-11.md) — текущий compliance-review;
- [operator-runtime-disclosure-checklist.md](./operator-runtime-disclosure-checklist.md) — ручная post-deploy/legal сверка;
- [secret-inventory.md](./secret-inventory.md) и [secret-rotation-checklist.md](./secret-rotation-checklist.md) — контур секретов и ротации.

## Operational specs

Использовать по конкретной задаче:
- [contract-analyzer.md](./contract-analyzer.md)
- [failure-recovery.md](./failure-recovery.md)
- [pd-incident-runbook.md](./pd-incident-runbook.md)
- [contract-ai-live-checklist.md](./contract-ai-live-checklist.md)
- [manual-regulatory-contour-checklist.md](./manual-regulatory-contour-checklist.md)
- [server-requirements.md](./server-requirements.md)
- [data-model.md](./data-model.md)

## Historical / archival docs

Следующие документы полезны как история решений, но не должны считаться source of truth без сверки с блоком выше:
- stage/release reports;
- audit/review документы;
- reconstruction/implementation concept docs;
- старые roadmap snapshots.

Типовые примеры архивных документов:
- `technical_audit_2026-03-09.md`
- `ux_ui_designer_review_2026-03-09.md`
- `stage-7-hardening-report.md`
- `stage-8-release-gate-site-reader-miniapp.md`
- `contract-ai-system-integration-concept.md`
- `contract-ai-system-integration-implementation-spec.md`
- `reconstruction-plan-site-reader-miniapp.md`

Правило:
- если архивный документ конфликтует с source-of-truth документами, доверять нужно source-of-truth документам.
