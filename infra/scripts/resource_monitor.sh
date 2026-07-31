#!/bin/bash
#
# Следит за диском, оперативной памятью и swap на production-хосте.
#
# Заменяет disk_monitor.sh, который на macOS не работал: он вызывал
# `df / --output=pcent` — это синтаксис GNU coreutils, а BSD-версия df в macOS
# такого флага не знает и падает с ошибкой. При включённом `set -e` скрипт
# завершался на первой же строке, поэтому оповещения не приходили никогда.
#
# Память добавлена потому, что исчерпание RAM на Mac Mini уже приводило к
# зависанию рабочего стола, и заметить это удалось только вручную.
#
# Запуск: раз в 5-10 минут через launchd или cron.
# Оповещения в Telegram отправляются, только если заданы ALERT_BOT_TOKEN и
# ALERT_CHAT_ID; без них скрипт просто пишет строку статуса в stdout, поэтому
# его безопасно запускать и до настройки бота.

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"

# cron запускает задачи с почти пустым окружением, поэтому токен бота нужно
# взять из .env самому. Значение читается точечно через grep, а не через
# `source`: файл содержит произвольные строки с кавычками и подстановками,
# и исполнять его целиком ради двух переменных небезопасно.
read_env_value() {
  local key="$1"
  [ -f "$ENV_FILE" ] || return 0
  sed -n "s/^${key}=//p" "$ENV_FILE" | head -n 1 | sed -e 's/^"//' -e 's/"$//'
}

ALERT_BOT_TOKEN="${ALERT_BOT_TOKEN:-$(read_env_value ALERT_BOT_TOKEN)}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-$(read_env_value ALERT_CHAT_ID)}"

# С этого хоста api.telegram.org по DNS не разрешается — запрос просто виснет
# до таймаута. Контейнеры обходят это через extra_hosts с прямым адресом,
# здесь делаем то же самое через --resolve. Значение берём из .env, чтобы
# смена адреса не требовала правки скрипта.
TELEGRAM_API_HOST_IP="${TELEGRAM_API_HOST_IP:-$(read_env_value TELEGRAM_API_HOST_IP)}"
TELEGRAM_API_HOST_IP="${TELEGRAM_API_HOST_IP:-149.154.167.220}"

DISK_THRESHOLD_PCT="${DISK_THRESHOLD_PCT:-85}"
MEMORY_THRESHOLD_PCT="${MEMORY_THRESHOLD_PCT:-92}"
SWAP_THRESHOLD_PCT="${SWAP_THRESHOLD_PCT:-90}"

notify() {
  local message="$1"
  echo "$message"
  if [ -n "${ALERT_BOT_TOKEN:-}" ] && [ -n "${ALERT_CHAT_ID:-}" ]; then
    curl -fsS --max-time 15 \
      --resolve "api.telegram.org:443:${TELEGRAM_API_HOST_IP}" \
      "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${ALERT_CHAT_ID}" \
      -d "text=${message}" >/dev/null || echo "warn: не удалось отправить оповещение в Telegram"
  fi
}

# `df -P` даёт переносимый формат вывода и работает и в macOS, и в Linux.
disk_usage_pct() {
  df -P / | awk 'NR==2 {gsub(/%/, "", $5); print $5}'
}

# Доля занятой оперативной памяти.
#
# В macOS нельзя считать занятость как active+wired+compressed по vm_stat:
# система намеренно держит свободных страниц около нуля, сжимает неиспользуемое
# и вытесняет неактивное. Такой расчёт показывал 76-80% занятости в момент,
# когда memory_pressure сообщал о 44% свободной памяти, то есть монитор слал бы
# ложные тревоги на здоровой системе.
#
# memory_pressure отражает реальное давление: он учитывает, что неактивные и
# сжатые страницы освобождаются по требованию.
memory_usage_pct() {
  if [ "$(uname -s)" = "Darwin" ]; then
    local free_pct
    free_pct=$(memory_pressure 2>/dev/null | awk '/free percentage/ { gsub(/%/, "", $NF); print $NF }')
    if [ -n "$free_pct" ]; then
      printf "%d" "$((100 - free_pct))"
    else
      # memory_pressure недоступен — отдаём 0, чтобы не поднимать ложную
      # тревогу по заведомо неверной метрике.
      printf "0"
    fi
  else
    free | awk '/^Mem:/ { if ($2 > 0) printf "%d", ($3 * 100) / $2; else print 0 }'
  fi
}

# Доля занятого swap. Постоянно забитый swap — признак того, что памяти уже
# не хватает, даже если система пока отвечает.
swap_usage_pct() {
  if [ "$(uname -s)" = "Darwin" ]; then
    sysctl vm.swapusage 2>/dev/null | awk '
      {
        for (i = 1; i <= NF; i++) {
          if ($i == "total") { gsub(/[^0-9.]/, "", $(i + 2)); total = $(i + 2) }
          if ($i == "used") { gsub(/[^0-9.]/, "", $(i + 2)); used = $(i + 2) }
        }
        if (total > 0) printf "%d", (used * 100) / total; else print 0
      }'
  else
    free | awk '/^Swap:/ { if ($2 > 0) printf "%d", ($3 * 100) / $2; else print 0 }'
  fi
}

disk=$(disk_usage_pct || echo 0)
memory=$(memory_usage_pct || echo 0)
swap=$(swap_usage_pct || echo 0)

problems=()
[ "${disk:-0}" -gt "$DISK_THRESHOLD_PCT" ] && problems+=("диск ${disk}%")
[ "${memory:-0}" -gt "$MEMORY_THRESHOLD_PCT" ] && problems+=("память ${memory}%")

# На macOS swap не является признаком нехватки памяти: система расширяет его
# динамически (на боевом хосте total вырос с 7 до 11 ГБ за сутки) и держит
# почти полным, поэтому процент заполнения почти всегда высокий. Триггерить по
# нему — гарантированные ложные тревоги, поэтому значение только показываем.
if [ "$(uname -s)" != "Darwin" ]; then
  [ "${swap:-0}" -gt "$SWAP_THRESHOLD_PCT" ] && problems+=("swap ${swap}%")
fi

if [ "${#problems[@]}" -gt 0 ]; then
  # IFS склеивает элементы только одним символом, поэтому собираем строку
  # вручную, чтобы получить читаемое перечисление через запятую с пробелом.
  joined=$(printf '%s, ' "${problems[@]}")
  joined=${joined%, }
  notify "⚠️ Ресурсы Mac Mini на пределе: ${joined}. Диск ${disk}%, память ${memory}%, swap ${swap}%."
  exit 0
fi

echo "ok: диск ${disk}%, память ${memory}%, swap ${swap}%"
