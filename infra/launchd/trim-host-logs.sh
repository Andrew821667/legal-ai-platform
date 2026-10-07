#!/bin/bash
# Подрезка журналов служб на Mac mini — раз в сутки, от root.
#
# Журналы контейнеров ограничены настройками Docker (10 МБ × 5), а журналы
# служб на самом хосте (launchd, cron: xray, туннели, сторожа, бэкап) — нет:
# xray-balancer.out.log дорос до 120 МБ, и рос бы дальше, пока не съел диск.
# Файл больше LIMIT_MB сжимается в <имя>.1.gz (прежняя такая копия
# заменяется) и очищается на месте: службы пишут с O_APPEND, после очистки
# продолжают с начала файла, перезапускать их не нужно.
#
# Устанавливается root-владельцем в /usr/local/sbin (см. plist рядом).
set -u

LIMIT_MB="${LIMIT_MB:-20}"
DIRS="${DIRS:-/Users/andrej/Library/Logs /Users/legalai/Library/Logs /Users/andrej/backups/legal-ai}"

for dir in $DIRS; do
  [ -d "$dir" ] || continue
  find "$dir" -maxdepth 1 -type f -name '*.log' -size +"${LIMIT_MB}"M -print0 |
    while IFS= read -r -d '' file; do
      before="$(du -h "$file" | cut -f1)"
      if gzip -c "$file" > "$file.1.gz.part" && mv "$file.1.gz.part" "$file.1.gz"; then
        : > "$file"
        echo "$(date '+%F %T') $file: $before → архив $(du -h "$file.1.gz" | cut -f1)"
      else
        rm -f "$file.1.gz.part"
        echo "$(date '+%F %T') $file: не удалось сжать, оставлен как есть"
      fi
    done
done
