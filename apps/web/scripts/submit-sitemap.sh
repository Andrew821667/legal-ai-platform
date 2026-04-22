#!/bin/bash

# Скрипт для отправки sitemap в поисковые системы

SITE_URL="https://ai-verdict.ru"
SITEMAP_URL="${SITE_URL}/sitemap.xml"

echo "🚀 Отправка sitemap в поисковые системы..."
echo ""

# Google
echo "📍 Отправка в Google..."
GOOGLE_PING="https://www.google.com/ping?sitemap=${SITEMAP_URL}"
curl -s "$GOOGLE_PING" > /dev/null
echo "✅ Google: $GOOGLE_PING"
echo ""

# Yandex
echo "📍 Отправка в Yandex..."
YANDEX_PING="https://webmaster.yandex.ru/ping?sitemap=${SITEMAP_URL}"
curl -s "$YANDEX_PING" > /dev/null
echo "✅ Yandex: $YANDEX_PING"
echo ""

# Bing (опционально)
echo "📍 Отправка в Bing..."
BING_PING="https://www.bing.com/ping?sitemap=${SITEMAP_URL}"
curl -s "$BING_PING" > /dev/null
echo "✅ Bing: $BING_PING"
echo ""

echo "✅ Готово! Sitemap отправлен во все поисковые системы."
echo ""
echo "Проверьте результаты через несколько дней в:"
echo "- Google Search Console: https://search.google.com/search-console"
echo "- Yandex.Webmaster: https://webmaster.yandex.ru"
