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
            // Боевой режим с 02.10.2026: месяцы в Report-Only на сайте,
            // кабинете, рабочем месте, мини-аппе и в админке дали одно
            // нарушение — веб-сокет Метрики (wss://mc.yandex.ru), он
            // добавлен. Что браузер всё-таки заблокирует, приходит в
            // /api/csp-report и пишется в журнал сайта: смотреть там, если
            // что-то на странице перестало работать.
            //
            // 'unsafe-inline' в script-src нужен Next.js для inline-скриптов
            // гидратации и счётчику Метрики. Убрать его можно только вместе с
            // переходом на nonce.
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              // challenges.cloudflare.com — капча Turnstile (появляется на
              // формах, только если заданы её ключи); yastatic.net — Метрика.
              // 'unsafe-eval' — только в `next dev` (горячая перезагрузка), в сборке его нет.
              `script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === 'production' ? '' : " 'unsafe-eval'"} https://mc.yandex.ru https://yastatic.net https://telegram.org https://challenges.cloudflare.com`,
              "style-src 'self' 'unsafe-inline'",
              // https://t.me и https://*.telegram.org — аватар профиля из
              // Telegram Login на странице /cabinet/profile, обычный <img>.
              "img-src 'self' data: blob: https://mc.yandex.ru https://t.me https://*.telegram.org",
              "font-src 'self' data:",
              // wss://mc.yandex.ru — Вебвизор Метрики.
              "connect-src 'self' https://mc.yandex.ru wss://mc.yandex.ru",
              // https://oauth.telegram.org — legacy-виджет входа рисует
              // кнопку и подтверждение внутри iframe с этого источника.
              // Обмен кода на токен идёт с сервера (route handler), CSP
              // браузера на него не действует. blob: — Вебвизор Метрики.
              "frame-src blob: https://mc.yandex.ru https://oauth.telegram.org https://challenges.cloudflare.com",
              "worker-src 'self' blob:",
              // Mini App открывается внутри клиента Telegram.
              "frame-ancestors 'self' https://web.telegram.org",
              "base-uri 'self'",
              "form-action 'self' https://oauth.telegram.org",
              "object-src 'none'",
              "report-uri /api/csp-report",
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
