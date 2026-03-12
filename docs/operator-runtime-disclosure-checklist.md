# Operator Runtime Disclosure Checklist

Обновлено: 2026-03-11

Цель:
- не забыть заполнить runtime-disclosure перед реальным использованием сервиса;
- синхронизировать `lead-bot`, `web` и публичные legal routes;
- отделить кодовые меры от ручной операционной проверки.

## 1. Обязательные runtime-поля

Заполнить в фактическом `.env` перед внешним запуском:

- `OPERATOR_NAME`
- `OPERATOR_INN`
- `OPERATOR_DETAILS`
- `PRIVACY_CONTACT_EMAIL`
- `PRIVACY_POLICY_URL`
- `TRANSBORDER_CONSENT_URL`
- `USER_AGREEMENT_URL`
- `AI_POLICY_URL`
- `MARKETING_CONSENT_URL`
- `NEXT_PUBLIC_OPERATOR_NAME`
- `NEXT_PUBLIC_OPERATOR_STATUS`
- `NEXT_PUBLIC_OPERATOR_INN`
- `NEXT_PUBLIC_OPERATOR_DETAILS`
- `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL`
- `NEXT_PUBLIC_CONTACT_PHONE`
- `NEXT_PUBLIC_CONTACT_TELEGRAM`

Важно:
- в `.env.example` и `apps/web/.env.example` эти поля могут быть пустыми намеренно, чтобы placeholder-значения не выглядели как готовые боевые реквизиты;
- source of truth здесь — фактический runtime `.env`, а не пример файла.

Минимальное требование:
- `OPERATOR_NAME` не должен оставаться generic значением, если сервис публичный;
- `OPERATOR_INN` и `OPERATOR_DETAILS` должны содержать реальные реквизиты или статус оператора;
- `PRIVACY_CONTACT_EMAIL` должен вести на реальный канал связи по ПД.
- `NEXT_PUBLIC_*` disclosure vars не должны расходиться с серверными значениями для `lead-bot`.

## 2. Что проверить в `lead-bot`

1. `/privacy`
   - есть имя оператора;
   - есть контакт по вопросам ПД;
   - текст не выглядит как заглушка.
2. `/transborder_consent`
   - текст соответствует фактическому ИИ-сценарию;
   - есть корректный статус согласия.
3. `/documents`
   - ссылки/кнопки ведут на актуальные документы.
4. Consent-экраны:
   - не содержат старых внешних URL;
   - не указывают на несуществующие страницы.

## 3. Что проверить в `web`

1. Открываются страницы:
   - `/privacy`
   - `/terms`
   - `/user-agreement`
   - `/transborder-consent`
   - `/marketing-consent`
   - `/ai-policy`
2. В legal-блоках и footer:
   - нет битых ссылок;
   - copy соответствует текущему оператору;
   - disclaimer не противоречит bot-flow.
3. Privacy page:
   - перечисляет только реально используемые processors/analytics;
   - retention wording не противоречит фактической модели.

## 4. Живая проверка после деплоя

1. Открыть все публичные legal routes в браузере на боевом домене.
2. Открыть те же документы из `lead-bot`.
3. Сверить:
   - operator name;
   - contact email;
   - policy links;
   - wording по трансграничной передаче и аналитике.
4. Зафиксировать дату и результат проверки в operational notes.

Команда для локальной контрольной проверки:
- `bash infra/scripts/runtime_compliance_audit.sh`

## 5. Когда чек-лист считается закрытым

Только если:
- runtime env заполнен реальными значениями;
- bot и web показывают одинаковый public policy contour;
- все legal URL живые и открываются без 404/redirect loop;
- владелец проекта вручную подтвердил это после актуального деплоя.
