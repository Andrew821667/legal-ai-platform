/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Redirects from old Vercel domain to new domain
  async redirects() {
    return [
      {
        source: '/:path*',
        has: [
          {
            type: 'host',
            value: 'legal-ai-website-iota.vercel.app',
          },
        ],
        destination: 'https://ai-verdict.ru/:path*',
        permanent: true, // 301 redirect
      },
      {
        source: '/:path*',
        has: [
          {
            type: 'host',
            // Next.js treats host matcher as RegExp source, so "*.vercel.app" is invalid.
            value: '(.+)\\.vercel\\.app',
          },
        ],
        destination: 'https://ai-verdict.ru/:path*',
        permanent: true, // 301 redirect
      },
    ];
  },

  // Security Headers
  async headers() {
    return [
      {
        source: '/images/visual-v2/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        source: '/:path*',
        headers: [
          {
            // Пока Report-Only: политика ничего не блокирует, а только пишет
            // нарушения в консоль браузера. Это осознанный первый шаг —
            // включать сразу в блокирующем режиме опасно, любой пропущенный
            // источник (аналитика, шрифт, встроенный скрипт) молча сломал бы
            // страницу в проде.
            //
            // Порядок перевода в боевой режим:
            //   1. Открыть основные страницы, Mini App и админку, собрать
            //      нарушения из консоли;
            //   2. дополнить директивы недостающими источниками;
            //   3. переименовать заголовок в 'Content-Security-Policy'.
            //
            // 'unsafe-inline' в script-src нужен Next.js для inline-скриптов
            // гидратации. Убрать его можно только вместе с переходом на nonce.
            key: 'Content-Security-Policy-Report-Only',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' https://mc.yandex.ru https://www.googletagmanager.com https://telegram.org",
              "style-src 'self' 'unsafe-inline'",
              // https://t.me и https://*.telegram.org — аватар профиля из
              // Telegram Login на странице /cabinet/profile, обычный <img>.
              "img-src 'self' data: blob: https://mc.yandex.ru https://www.google-analytics.com https://www.googletagmanager.com https://t.me https://*.telegram.org",
              "font-src 'self' data:",
              "connect-src 'self' https://mc.yandex.ru https://www.google-analytics.com https://www.googletagmanager.com",
              // https://oauth.telegram.org — legacy-виджет входа рисует
              // кнопку и подтверждение внутри iframe с этого источника.
              // Обмен кода на токен идёт с сервера (route handler), CSP
              // браузера на него не действует.
              "frame-src https://mc.yandex.ru https://oauth.telegram.org",
              // Mini App открывается внутри клиента Telegram.
              "frame-ancestors 'self' https://web.telegram.org",
              "base-uri 'self'",
              "form-action 'self' https://oauth.telegram.org",
              "object-src 'none'",
            ].join('; '),
          },
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on'
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload'
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block'
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin'
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()'
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
