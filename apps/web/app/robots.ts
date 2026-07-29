import { MetadataRoute } from 'next'
import { SEO_SITE_URL } from '@/lib/seo'

export default function robots(): MetadataRoute.Robots {
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
      {
        userAgent: 'Bingbot',
        allow: '/',
        disallow: privatePaths,
      },
      {
        userAgent: 'OAI-SearchBot',
        allow: '/',
        disallow: privatePaths,
      },
      {
        userAgent: 'ChatGPT-User',
        allow: '/',
        disallow: privatePaths,
      },
    ],
    sitemap: `${SEO_SITE_URL}/sitemap.xml`,
    host: SEO_SITE_URL,
  }
}
