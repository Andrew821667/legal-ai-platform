#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
SITE_URL="${SITE_URL:-https://ai-verdict.ru}"
SITEMAP_URL="${SITEMAP_URL:-${SITE_URL%/}/sitemap.xml}"
TARGET_DATE="${INDEXNOW_LASTMOD:-$(date -u +%F)}"
KEY_FILE="${INDEXNOW_KEY_FILE:-$APP_DIR/apps/web/public/b4fe13ccb289b2cb74669ac21583f8af224efe317e2f9a79c23b2bb57d5e1fe4.txt}"

if [ ! -r "$KEY_FILE" ]; then
  echo "IndexNow skipped: key file not found."
  exit 0
fi

key="$(tr -d '[:space:]' < "$KEY_FILE")"
key_name="$(basename "$KEY_FILE")"
key_url="${SITE_URL%/}/$key_name"
sitemap_tmp="$(mktemp)"
trap 'rm -f "$sitemap_tmp"' EXIT

if [ "$#" -eq 0 ]; then
  curl -fsS "$SITEMAP_URL" -o "$sitemap_tmp"
fi

url_list="$(
  INDEXNOW_SITE_URL="$SITE_URL" python3 - "$sitemap_tmp" "$TARGET_DATE" "$@" <<'PY'
import json
import os
import sys
import xml.etree.ElementTree as ET

sitemap_path, target_date, *explicit = sys.argv[1:]
if explicit:
    base_url = os.environ["INDEXNOW_SITE_URL"].rstrip("/")
    urls = [url if url.startswith("http") else f"{base_url}{url}" for url in explicit]
else:
    root = ET.parse(sitemap_path).getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for item in root.findall("sm:url", ns):
        loc = item.findtext("sm:loc", default="", namespaces=ns)
        lastmod = item.findtext("sm:lastmod", default="", namespaces=ns)
        if loc and lastmod.startswith(target_date):
            urls.append(loc)

print(json.dumps(urls, ensure_ascii=False))
PY
)"

url_count="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<< "$url_list")"
if [ "$url_count" -eq 0 ]; then
  echo "IndexNow: no URLs with lastmod $TARGET_DATE."
  exit 0
fi

payload="$(
  python3 - "$SITE_URL" "$key" "$key_url" "$url_list" <<'PY'
import json
import sys
from urllib.parse import urlparse

site_url, key, key_url, urls = sys.argv[1:]
print(json.dumps({
    "host": urlparse(site_url).netloc,
    "key": key,
    "keyLocation": key_url,
    "urlList": json.loads(urls),
}, ensure_ascii=False))
PY
)"

if [ "${INDEXNOW_DRY_RUN:-0}" = "1" ]; then
  echo "IndexNow dry run prepared $url_count updated URLs."
  exit 0
fi

curl -fsS \
  -X POST \
  -H "Content-Type: application/json; charset=utf-8" \
  --data "$payload" \
  "https://yandex.com/indexnow" \
  >/dev/null

echo "IndexNow accepted $url_count updated URLs."
