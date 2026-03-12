#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

failures=0
warnings=0

print_section() {
  printf '\n[%s]\n' "$1"
}

report_ok() {
  printf '  OK   %s\n' "$1"
}

report_warn() {
  printf '  WARN %s\n' "$1"
  warnings=$((warnings + 1))
}

report_fail() {
  printf '  FAIL %s\n' "$1"
  failures=$((failures + 1))
}

read_var() {
  local name="$1"
  printf '%s' "${!name-}"
}

is_weak_value() {
  local value="${1,,}"
  case "$value" in
    ""|change_me*|changeme*|replace_me*|replace-with-*|example*|your_*|your-*|admin123|legalai|legalai_app|legalai_platform)
      return 0
      ;;
  esac
  return 1
}

check_required_secret() {
  local name="$1"
  local value
  value="$(read_var "$name")"
  if [[ -z "$value" ]]; then
    report_fail "$name is missing"
    return
  fi
  if is_weak_value "$value"; then
    report_fail "$name looks weak or placeholder"
    return
  fi
  report_ok "$name is set"
}

check_optional_secret() {
  local name="$1"
  local value
  value="$(read_var "$name")"
  if [[ -z "$value" ]]; then
    report_warn "$name is not set"
    return
  fi
  if is_weak_value "$value"; then
    report_warn "$name looks weak or placeholder"
    return
  fi
  report_ok "$name is set"
}

check_required_public_disclosure() {
  local name="$1"
  local value
  value="$(read_var "$name")"
  if [[ -z "$value" ]]; then
    report_warn "$name is missing"
    return
  fi
  if is_weak_value "$value"; then
    report_warn "$name looks placeholder-like"
    return
  fi
  report_ok "$name is set"
}

check_internal_route() {
  local route="$1"
  if ! docker ps --format '{{.Names}}' | grep -qx 'legal-ai-web'; then
    report_warn "legal-ai-web container is not running; skipped route $route"
    return
  fi

  local status
  status="$(docker exec legal-ai-web node -e "fetch('http://127.0.0.1:3000${route}').then((r)=>{console.log(r.status)}).catch(()=>{console.log('ERR')})" 2>/dev/null | tail -n1)"

  if [[ "$status" == "200" ]]; then
    report_ok "route ${route} -> 200"
    return
  fi

  report_warn "route ${route} -> ${status:-unknown}"
}

check_postgres_consistency() {
  if [[ -z "${DATABASE_URL:-}" || -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" || -z "${POSTGRES_DB:-}" ]]; then
    report_warn "DATABASE_URL / POSTGRES_* consistency check skipped because one of the values is missing"
    return
  fi

  [[ "$DATABASE_URL" == *"//${POSTGRES_USER}:"* ]] \
    && report_ok "DATABASE_URL user matches POSTGRES_USER" \
    || report_warn "DATABASE_URL user does not match POSTGRES_USER"

  [[ "$DATABASE_URL" == *":${POSTGRES_PASSWORD}@"* ]] \
    && report_ok "DATABASE_URL password matches POSTGRES_PASSWORD" \
    || report_warn "DATABASE_URL password does not match POSTGRES_PASSWORD"

  [[ "$DATABASE_URL" == */"${POSTGRES_DB}" ]] \
    && report_ok "DATABASE_URL database matches POSTGRES_DB" \
    || report_warn "DATABASE_URL database does not match POSTGRES_DB"
}

print_section "Required runtime secrets"
for name in \
  POSTGRES_PASSWORD \
  DATABASE_URL \
  API_KEY_BOT \
  API_KEY_NEWS \
  API_KEY_ADMIN \
  LEAD_BOT_TOKEN \
  TELEGRAM_BOT_TOKEN \
  NEWS_ADMIN_BOT_TOKEN \
  READER_BOT_TOKEN \
  TELEGRAM_API_ID \
  TELEGRAM_API_HASH \
  OPENAI_API_KEY \
  ADMIN_PANEL_PASSWORD_HASH \
  ADMIN_PANEL_TOTP_SECRET \
  ADMIN_PANEL_SESSION_SECRET
do
  check_required_secret "$name"
done

print_section "Optional / integration secrets"
for name in \
  API_KEY_WORKER \
  ALERT_BOT_TOKEN \
  DEEPSEEK_API_KEY \
  PERPLEXITY_API_KEY \
  GA4_CREDENTIALS \
  YM_ACCESS_TOKEN \
  GITHUB_TOKEN \
  SMTP_PASSWORD
do
  check_optional_secret "$name"
done

print_section "Lead-bot operator disclosure runtime"
for name in \
  OPERATOR_NAME \
  OPERATOR_INN \
  OPERATOR_DETAILS \
  PRIVACY_CONTACT_EMAIL \
  PRIVACY_POLICY_URL \
  TRANSBORDER_CONSENT_URL \
  USER_AGREEMENT_URL \
  AI_POLICY_URL \
  MARKETING_CONSENT_URL
do
  check_required_public_disclosure "$name"
done

print_section "Postgres runtime consistency"
check_postgres_consistency

print_section "Web public disclosure runtime"
for name in \
  NEXT_PUBLIC_OPERATOR_NAME \
  NEXT_PUBLIC_OPERATOR_STATUS \
  NEXT_PUBLIC_OPERATOR_INN \
  NEXT_PUBLIC_OPERATOR_DETAILS \
  NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL \
  NEXT_PUBLIC_CONTACT_PHONE \
  NEXT_PUBLIC_CONTACT_TELEGRAM
do
  check_required_public_disclosure "$name"
done

print_section "Internal legal routes"
for route in \
  /privacy \
  /terms \
  /user-agreement \
  /transborder-consent \
  /marketing-consent \
  /ai-policy
do
  check_internal_route "$route"
done

print_section "Summary"
printf '  failures: %s\n' "$failures"
printf '  warnings: %s\n' "$warnings"

if (( failures > 0 )); then
  exit 1
fi
