import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://ai-verdict.ru'
  const privatePaths = ['/api', '/admin', '/monitor', '/miniapp/lead', '/miniapp/profile']

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: privatePaths,
      },
      {
        userAgent: 'Googlebot',
        allow: '/',
        disallow: privatePaths,
        crawlDelay: 1,
      },
      {
        userAgent: 'Yandex',
        allow: '/',
        disallow: privatePaths,
        crawlDelay: 1,
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  }
}
