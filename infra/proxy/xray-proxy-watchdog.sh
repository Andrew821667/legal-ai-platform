#!/bin/bash
# Watchdog канала до Telegram через xray-balancer (192.168.64.1:10811).
#
# Зачем: адреса VPN-узлов постоянно ротируются из-за блокировок, и пул может
# целиком протухнуть между плановыми синхронизациями (раз в 30 минут). Боты и
# публикация постов в этот промежуток молчат. Watchdog ловит это за пару минут.
#
# Логика сознательно осторожная, как в ss-watchdog.sh: одна неудачная проверка
# ничего не запускает (бывает разрыв на ровном месте), действие — со второй
# подряд. Сначала чиним сами (пересборка пула отбросит мёртвые узлы), и только
# если и это не помогло несколько раз — зовём человека.
#
# Хуки для проверки (по умолчанию — боевое поведение):
#   XRAY_WATCHDOG_FORCE_FAIL=1   считать проверку проваленной
#   XRAY_WATCHDOG_HEARTBEAT=1    писать в лог каждый запуск, не только действия

LOG="/Users/andrej/Library/Logs/xray-proxy-watchdog.log"
STATE="/var/run/xray-proxy-watchdog.state"
PROXY="http://192.168.64.1:10811"
PROBE_URL="https://api.telegram.org"
ENV_FILE="/Users/legalai/projects/legal-ai-platform/.env"
# Через сколько неудачных проверок подряд звать человека (2 мин * 5 = ~10 мин).
ALERT_AFTER=5

ts() { date "+%Y-%m-%d %H:%M:%S"; }
note() { echo "$(ts) $*" >> "$LOG"; }

fails=0
[ -f "$STATE" ] && fails=$(cat "$STATE" 2>/dev/null | tr -cd '0-9')
[ -z "$fails" ] && fails=0

if [ "${XRAY_WATCHDOG_FORCE_FAIL:-0}" = "1" ]; then
  code="000"
else
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 12 -x "$PROXY" "$PROBE_URL" 2>/dev/null)
fi

if [ "$code" != "000" ] && [ -n "$code" ]; then
  if [ "$fails" -gt 0 ]; then
    note "OK (http=$code) — канал восстановился после $fails неудачных проверок"
  elif [ "${XRAY_WATCHDOG_HEARTBEAT:-0}" = "1" ]; then
    note "OK (http=$code)"
  fi
  rm -f "$STATE"
  exit 0
fi

fails=$((fails + 1))
echo "$fails" > "$STATE"

if [ "$fails" -eq 1 ]; then
  # Первая неудача — может быть разрыв на ровном месте, ждём подтверждения.
  note "проверка не прошла (1) — жду подтверждения, ничего не трогаю"
  exit 0
fi

note "проверка не прошла ($fails) — пересобираю пул узлов"
/bin/launchctl kickstart -k system/ru.legalai.xray-balancer-sync >>"$LOG" 2>&1

# Повторная проверка после пересборки: пулу нужно время на health-check узлов.
sleep 25
recheck=$(curl -s -o /dev/null -w "%{http_code}" --max-time 12 -x "$PROXY" "$PROBE_URL" 2>/dev/null)
if [ "$recheck" != "000" ] && [ -n "$recheck" ]; then
  note "восстановлено пересборкой пула (http=$recheck)"
  rm -f "$STATE"
  exit 0
fi

note "пересборка не помогла (http=$recheck)"

if [ "$fails" -lt "$ALERT_AFTER" ]; then
  exit 0
fi

# Зовём человека. Отправляем через любой живой прокси: балансировщик лежит,
# но соседние инстансы обычно живы — иначе сообщение не доставить вовсе.
TOKEN=$(grep -m1 '^NEWS_ADMIN_BOT_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
[ -z "$TOKEN" ] && TOKEN=$(grep -m1 '^LEAD_BOT_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
CHAT=$(grep -m1 '^NEWS_ADMIN_IDS=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | cut -d, -f1)
[ -z "$CHAT" ] && CHAT=$(grep -m1 '^ADMIN_TELEGRAM_ID=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)

if [ -z "$TOKEN" ] || [ -z "$CHAT" ]; then
  note "ALERT не отправлен: в .env нет токена бота или id администратора"
  exit 0
fi

TEXT="🔴 Прокси до Telegram не работает ${fails} проверок подряд (~$((fails * 2)) мин). Пересборка пула не помогла — боты и публикация постов стоят. Скорее всего, все узлы подписки заблокированы: нужна свежая подписка или ручная проверка у провайдера."

for p in "http://127.0.0.1:11808" "http://127.0.0.1:13808" "http://127.0.0.1:14808" "$PROXY"; do
  out=$(curl -s -o /dev/null -w "%{http_code}" --max-time 12 -x "$p" \
    --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=${TEXT}" \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" 2>/dev/null)
  if [ "$out" = "200" ]; then
    note "ALERT отправлен администратору через $p"
    # Счётчик не сбрасываем, но и спамить не хотим: следующий алерт — когда
    # счётчик снова дорастёт до порога.
    echo "0" > "$STATE"
    exit 0
  fi
done
note "ALERT не доставлен: ни один прокси не пропустил сообщение"
