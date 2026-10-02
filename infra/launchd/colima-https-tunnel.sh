#!/bin/bash
# Порт 443 сайта — из виртуальной машины Colima на внешние адреса Mac mini.
#
# Docker на Mac mini работает в Colima (Lima): порты контейнеров на хост
# пробрасывает limactl hostagent через ssh от имени andrej. macOS разрешает
# не-root занять порт 443 только на всех адресах сразу (0.0.0.0), а 443 на
# адресах Tailscale держит Tailscale Funnel MAX-бота (inwhite-ai-demo; MAX
# принимает вебхук только на 443). Поэтому штатный проброс 443 не встаёт, и
# после пересоздания Caddy сайт отвечал 000 (02.10.2026).
#
# Этот туннель — от root: root может занять 443 на конкретных адресах
# (en0, en1, 127.0.0.1), не трогая адресов Tailscale. Соединение — к тому же
# sshd виртуальной машины, что у Lima; пересоздание Caddy туннель не рвёт.
# Порт sshd меняется при перезапуске Colima — читаем его заново при каждом
# старте; при смене адресов сети выходим, launchd запустит заново.
#
# Устанавливается root-владельцем в /usr/local/sbin (см. plist рядом):
# root не должен исполнять файл из каталога, куда пишет пользователь деплоя.
set -u

LIMA_DIR=/Users/andrej/.colima/_lima/colima
KEY=/Users/andrej/.colima/_lima/_config/user

addresses() {
  { ipconfig getifaddr en0; ipconfig getifaddr en1; echo 127.0.0.1; } 2>/dev/null | sort -u | tr '\n' ' '
}

# Ждём виртуальную машину: после перезагрузки Colima поднимается не сразу.
while true; do
  port="$(awk '$1 == "Port" { print $2 }' "$LIMA_DIR/ssh.config" 2>/dev/null)"
  if [ -n "$port" ] && nc -z 127.0.0.1 "$port" 2>/dev/null; then
    break
  fi
  sleep 10
done

ips="$(addresses)"
forwards=()
for ip in $ips; do
  forwards+=(-L "$ip:443:[::]:443")
done
echo "$(date '+%F %T') туннель 443: адреса $ips, sshd Colima :$port"

/usr/bin/ssh -F /dev/null -i "$KEY" \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o BatchMode=yes -o LogLevel=ERROR -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes -p "$port" -N "${forwards[@]}" andrej@127.0.0.1 &
pid=$!

# Обрыв ssh замечаем за 5 секунд (в /bin/bash 3.2 нет wait -n), смену
# адресов сети — раз в минуту.
ticks=0
while kill -0 "$pid" 2>/dev/null; do
  sleep 5
  ticks=$((ticks + 1))
  if [ $((ticks % 12)) -eq 0 ] && [ "$(addresses)" != "$ips" ]; then
    echo "$(date '+%F %T') адреса сети сменились — перезапуск туннеля"
    kill "$pid"
    break
  fi
done
wait "$pid"
exit 1
