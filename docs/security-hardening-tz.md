# Security Hardening TZ

## Goal

Strengthen `Legal-ai-platform` against malicious bots, automated spam, credential abuse, API misuse, and unauthorized access. The first implementation wave focuses on `lead-bot`, public web lead intake, `web-admin`, and the production perimeter.

## Scope

Included:
- `lead-bot` legacy protection
- public website lead intake
- `web-admin` authentication hardening
- production perimeter for `core-api`
- security logging, quarantine, alerts, and tests

Excluded:
- enterprise IAM / SSO
- full cloud WAF rollout
- WebAuthn in the first implementation wave

## Stage 1. Lead-bot Human-Only Gate and Anti-Abuse

### Entry points
- `apps/lead-bot/legacy/bot.py`
- `apps/lead-bot/legacy/security.py`
- `apps/lead-bot/legacy/handlers/user.py`
- `apps/lead-bot/legacy/handlers/callbacks.py`
- `apps/lead-bot/legacy/database.py`

### Functional requirements
- Introduce a single security gate that runs before business logic for:
  - `message`
  - `callback_query`
  - `business_message`
  - commands
  - non-text updates
- The gate must block or isolate:
  - `from_user.is_bot == true`
  - self-messages
  - `via_bot != null`
  - `sender_business_bot != null`
  - private updates where `chat.id != from_user.id`
  - updates without a stable user identity unless explicitly allowlisted
- Each decision must be classified as one of:
  - `allow`
  - `blocked_soft`
  - `quarantine`
  - `blacklist`
- Supported inbound user content types:
  - `text`
  - `contact`
  - `document` for current demo flow
  - `photo` for current demo flow
- Unsupported content types must be:
  - rejected softly with a neutral message, or
  - logged as suspicious if repeated or clearly abnormal

### Abuse controls
- Rate limit text messages by user.
- Add callback-specific limits:
  - total callbacks per minute
  - duplicate callback suppression within a short burst window
- Add non-text limits:
  - allowed non-text events per hour
  - repeated unsupported payload suppression
- Add attachment hardening for supported inbound files:
  - document MIME allowlist
  - document extension allowlist fallback
  - document max size
  - photo max size
- Validate deep-link payloads by allowlist regex before state mutation or lead creation.

### Quarantine policy
- Add temporary isolation instead of immediate permanent blocking for the first wave of suspicious activity.
- Suggested escalation:
  - 1-2 suspicious events: `blocked_soft`
  - 3 suspicious events in the active window: `quarantine`
  - repeated activity after quarantine or severe non-human signals: `blacklist`

### Admin alerts
- Send alerts to admin for:
  - detected bot actor
  - quarantine activation
  - blacklist activation
  - burst suspicious activity over threshold

## Stage 1. Security Journal and Persistence

### New persistence
- Add `security_incidents` table with:
  - `id`
  - `telegram_user_id`
  - `chat_id`
  - `update_id`
  - `update_type`
  - `action`
  - `reason_code`
  - `severity`
  - `payload_json`
  - `created_at`
- Add `security_quarantine` table with:
  - `telegram_user_id`
  - `status`
  - `reason_code`
  - `strikes`
  - `quarantined_until`
  - `created_at`
  - `updated_at`
- Add a generic action event table for callback and non-text throttling.

### Logging rules
- Every blocked, quarantined, or blacklisted action must create an incident record.
- Sensitive payloads must be reduced or masked in logs and DB records.
- Raw secrets, full tokens, and full contact data must never be persisted in security logs.

## Stage 2. Public Lead Form Protection

### Entry point
- `apps/web/app/api/leads/route.ts`

### Requirements
- Add honeypot hidden field.
- Add minimum form fill time validation.
- Add rate limit by IP.
- Add rate limit by normalized contact.
- Add deduplication by fingerprint.
- Add adaptive challenge support via Turnstile.
- Return:
  - `200` with silent drop for honeypot and time-trap hits
  - `429` for rate limit
  - `200` with no duplicate creation for deduped submissions

## Stage 3. Production Perimeter Hardening

### Entry points
- `infra/compose/docker-compose.prod.yml`
- `infra/caddy/Caddyfile`

### Requirements
- `core-api` must not be exposed on public `0.0.0.0:8000` in production.
- External traffic must go through reverse proxy only.
- Add security response headers for web/admin routes.
- Reduce direct attack surface for API and admin endpoints.

## Stage 4. Web Admin Hardening

### Entry points
- `apps/web/app/api/admin/auth/route.ts`
- `apps/web/lib/admin-session.ts`

### Requirements
- Replace plain-text admin password with `ADMIN_PANEL_PASSWORD_HASH` based on `bcrypt`.
- Add TOTP as the second factor.
- Move login throttling to persistent storage.
- Add revocable sessions with stable session IDs.
- Audit successful login, failed login, logout, and forced revocation.

## Stage 5. Repository Security Automation

### Entry points
- `.github/dependabot.yml`
- `.github/workflows/security.yml`
- `.gitleaks.toml`

### Requirements
- Enable scheduled dependency update PRs for `github-actions`, `npm`, `pip`, and tracked Dockerfiles.
- Add automated secret scanning for pushes and pull requests.
- Add CodeQL analysis for Python and JavaScript/TypeScript.
- Add dependency review checks on pull requests.

## Non-Functional Requirements
- All new controls must be feature-flag driven.
- All thresholds must be configurable via env.
- Real user UX must remain stable for normal flows.
- Every security reject must have a machine-readable `reason_code`.
- Security changes must preserve backward-compatible lead-bot business flow where possible.

## Environment Variables

Lead-bot:
- `BUSINESS_OPERATOR_TELEGRAM_IDS`
- `SECURITY_HUMAN_ONLY_ENABLED`
- `SECURITY_CALLBACKS_PER_MINUTE`
- `SECURITY_CALLBACK_DUPLICATE_WINDOW_SECONDS`
- `SECURITY_CALLBACK_DUPLICATE_BURST`
- `SECURITY_NON_TEXT_PER_HOUR`
- `SECURITY_ALLOWED_DOCUMENT_MIME_PREFIXES`
- `SECURITY_ALLOWED_DOCUMENT_EXTENSIONS`
- `SECURITY_DOCUMENT_MAX_BYTES`
- `SECURITY_PHOTO_MAX_BYTES`
- `SECURITY_QUARANTINE_MINUTES`
- `SECURITY_QUARANTINE_STRIKES`
- `SECURITY_BLACKLIST_STRIKES`
- `SECURITY_ALERT_BURST_THRESHOLD`

Web lead intake:
- `LEAD_FORM_HONEYPOT_FIELD`
- `LEAD_FORM_MIN_SUBMIT_SECONDS`
- `LEAD_FORM_IP_MAX_ATTEMPTS`
- `LEAD_FORM_IP_WINDOW_SECONDS`
- `LEAD_FORM_CONTACT_MAX_ATTEMPTS`
- `LEAD_FORM_CHALLENGE_MODE`
- `TURNSTILE_SECRET_KEY`
- `TURNSTILE_SITE_KEY`

Web admin:
- `ADMIN_PANEL_PASSWORD_HASH`
- `ADMIN_PANEL_TOTP_SECRET`
- `ADMIN_SESSION_MAX_AGE_SECONDS`
- `ADMIN_SESSION_MAX_CONCURRENT`

## Testing Requirements

Unit:
- block `from_user.is_bot`
- block `via_bot`
- block invalid private sender/chat mapping
- callback burst-limit
- quarantine escalation
- document MIME / extension filtering
- document / photo size limits
- deep-link allowlist validation

Integration:
- real user flow passes without regression
- malicious actor cannot create leads or mutate state
- security incidents are written to DB
- quarantine persists across manager restart

Smoke:
- existing lead-bot smoke flows remain operational
- repository security workflow files are present and valid YAML/TOML

## Acceptance Criteria
- Telegram updates from bot actors do not reach business logic.
- Suspicious callback floods do not mutate state.
- Security decisions create an audit trail.
- Quarantine survives process restart.
- Lead-bot business flows for human users still work.
- The implementation is covered by automated tests for the new controls.
