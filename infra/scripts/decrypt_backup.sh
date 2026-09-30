#!/usr/bin/env bash
# Расшифровать копию бэкапа с Яндекс Диска (legal_ai_ГГГГММДД_ччммсс.tar.enc).
#
#   infra/scripts/decrypt_backup.sh legal_ai_20260930_033000.tar.enc [файл-ключа]
#
# Ключ — ~/.config/legalai/backup.key на Mac mini или копия из менеджера
# паролей, сохранённая в файл. Работает на любом Mac (системный openssl).
# Результат — папка legal_ai_…/ рядом: дамп базы (.dump), база бота (.db) и
# SHA256SUMS; суммы сверяются сразу. Дамп восстанавливать —
# infra/scripts/restore_postgres.sh (затирает живую базу!) или restore_drill.sh.
set -euo pipefail

archive="${1:?Укажите файл .tar.enc}"
key="${2:-$HOME/.config/legalai/backup.key}"
[ -r "$archive" ] || { echo "Нет файла $archive" >&2; exit 1; }
[ -r "$key" ] || { echo "Нет ключа $key" >&2; exit 1; }

out_dir="$(dirname "$archive")"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -pass "file:$key" -in "$archive" \
  | tar -C "$out_dir" -xf -
name="$(basename "$archive" .tar.enc)"
(cd "$out_dir/$name" && shasum -a 256 -c SHA256SUMS)
echo "Готово: $out_dir/$name"
