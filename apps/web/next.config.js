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
        destination: 'https://legalaipro.ru/:path*',
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
        destination: 'https://legalaipro.ru/:path*',
        permanent: true, // 301 redirect
      },
    ];
  },

  // Security Headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
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
