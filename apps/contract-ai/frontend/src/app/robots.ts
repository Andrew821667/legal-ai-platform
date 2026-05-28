import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru'

  return {
    rules: [
      {
        userAgent: '*',
        allow: ['/', '/pricing', '/privacy', '/terms'],
        disallow: ['/api/', '/dashboard/', '/contracts/', '/login', '/register'],
      },
      {
        userAgent: 'Googlebot',
        allow: ['/', '/pricing', '/privacy', '/terms'],
        disallow: ['/api/', '/dashboard/', '/contracts/', '/login', '/register'],
      },
      {
        userAgent: 'Yandex',
        allow: ['/', '/pricing', '/privacy', '/terms'],
        disallow: ['/api/', '/dashboard/', '/contracts/', '/login', '/register'],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  }
}
