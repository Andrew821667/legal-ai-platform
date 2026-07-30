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

DISK_THRESHOLD_PCT="${DISK_THRESHOLD_PCT:-85}"
MEMORY_THRESHOLD_PCT="${MEMORY_THRESHOLD_PCT:-92}"
SWAP_THRESHOLD_PCT="${SWAP_THRESHOLD_PCT:-90}"

notify() {
  local message="$1"
  echo "$message"
  if [ -n "${ALERT_BOT_TOKEN:-}" ] && [ -n "${ALERT_CHAT_ID:-}" ]; then
    curl -fsS --max-time 15 "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${ALERT_CHAT_ID}" \
      -d "text=${message}" >/dev/null || echo "warn: не удалось отправить оповещение в Telegram"
  fi
}

# `df -P` даёт переносимый формат вывода и работает и в macOS, и в Linux.
disk_usage_pct() {
  df -P / | awk 'NR==2 {gsub(/%/, "", $5); print $5}'
}

# Доля занятой оперативной памяти.
memory_usage_pct() {
  if [ "$(uname -s)" = "Darwin" ]; then
    # vm_stat отдаёт счётчики в страницах; размер страницы берём из заголовка,
    # чтобы не зашивать 4096 или 16384 под конкретное железо.
    vm_stat | awk '
      /page size of/ { for (i = 1; i <= NF; i++) if ($i == "of") { page = $(i + 1); break } }
      /^Pages free/ { gsub(/\./, "", $3); free = $3 }
      /^Pages active/ { gsub(/\./, "", $3); active = $3 }
      /^Pages inactive/ { gsub(/\./, "", $3); inactive = $3 }
      /^Pages speculative/ { gsub(/\./, "", $3); spec = $3 }
      /^Pages wired down/ { gsub(/\./, "", $4); wired = $4 }
      /^Pages occupied by compressor/ { gsub(/\./, "", $5); compressed = $5 }
      END {
        total = free + active + inactive + spec + wired + compressed
        if (total <= 0) { print 0; exit }
        used = active + wired + compressed
        printf "%d", (used * 100) / total
      }'
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
[ "${swap:-0}" -gt "$SWAP_THRESHOLD_PCT" ] && problems+=("swap ${swap}%")

if [ "${#problems[@]}" -gt 0 ]; then
  # IFS склеивает элементы только одним символом, поэтому собираем строку
  # вручную, чтобы получить читаемое перечисление через запятую с пробелом.
  joined=$(printf '%s, ' "${problems[@]}")
  joined=${joined%, }
  notify "⚠️ Ресурсы Mac Mini на пределе: ${joined}. Диск ${disk}%, память ${memory}%, swap ${swap}%."
  exit 0
fi

echo "ok: диск ${disk}%, память ${memory}%, swap ${swap}%"
