/**
 * Структурированные данные Schema.org для улучшения SEO
 * Критично для YMYL-сайтов (юридические услуги)
 */

interface StructuredDataProps {
  siteUrl?: string;
}

export default function StructuredData({ siteUrl = 'https://legalaipro.ru' }: StructuredDataProps) {
  // Organization Schema
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    "name": "Legal AI PRO",
    "alternateName": "LegalAIPro",
    "url": siteUrl,
    "description": "Профессиональная команда юристов-разработчиков, создающих AI-решения для автоматизации юридической работы. 20+ лет опыта в юриспруденции и разработке.",
    "foundingDate": "2020",
    "slogan": "Юристы, которые сами пишут код",
    "knowsAbout": [
      "Искусственный интеллект",
      "Юридическая автоматизация",
      "Machine Learning",
      "Legal Tech",
      "YandexGPT",
      "GigaChat",
      "Договорная работа",
      "Судебная практика",
      "Due Diligence",
      "Налоговый комплаенс"
    ],
    "areaServed": {
      "@type": "Country",
      "name": "Россия"
    },
    "contactPoint": {
      "@type": "ContactPoint",
      "contactType": "customer service",
      "telephone": "+7-909-233-09-09",
      "email": "a.popov.gv@gmail.com",
      "availableLanguage": ["Russian", "English"],
      "areaServed": "RU"
    },
    "sameAs": [
      "https://t.me/legal_ai_pro",
      "https://github.com/Andrew821667/legal-ai-website"
    ]
  };

  // Professional Service Schema
  const serviceSchema = {
    "@context": "https://schema.org",
    "@type": "ProfessionalService",
    "@id": `${siteUrl}/#service`,
    "name": "Legal AI PRO - Автоматизация юридической работы",
    "serviceType": "Legal Technology & AI Development",
    "provider": {
      "@id": `${siteUrl}/#organization`
    },
    "areaServed": {
      "@type": "Country",
      "name": "Россия"
    },
    "hasOfferCatalog": {
      "@type": "OfferCatalog",
      "name": "AI Legal Services",
      "itemListElement": [
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Автоматизация договорной работы",
            "description": "AI-анализ договоров, выявление рисков, автоматическая генерация документов. Сокращение времени проверки с 2-3 часов до 5-10 минут.",
            "url": `${siteUrl}/services/contracts-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Судебная и претензионная работа",
            "description": "Автоматизация мониторинга арбитражных дел, анализ судебной практики, генерация процессуальных документов.",
            "url": `${siteUrl}/services/litigation-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Корпоративное право и M&A",
            "description": "Автоматизация Due Diligence, корпоративный документооборот. Сокращение времени проверки с 2-3 недель до 2 дней.",
            "url": `${siteUrl}/services/corporate-ma-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Комплаенс и регуляторный контроль с AI",
            "description": "Мониторинг изменений законодательства, прогнозирование рисков и автоматическая проверка соответствия.",
            "url": `${siteUrl}/services/compliance-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Налоговый комплаенс с AI",
            "description": "Мониторинг налоговых изменений, анализ налоговых рисков и автоматизация регулярной отчетности.",
            "url": `${siteUrl}/services/tax-compliance-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Земельное право с AI",
            "description": "Анализ правоустанавливающих документов, кадастровых данных и сопровождение земельных сделок.",
            "url": `${siteUrl}/services/land-law-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Юридическая аналитика с AI",
            "description": "Риск-дашборды, KPI юридической функции и аналитика для управленческих решений.",
            "url": `${siteUrl}/services/legal-analytics-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Кастомные AI-решения",
            "description": "Разработка индивидуальных AI-систем для автоматизации специфических юридических задач вашего бизнеса.",
            "url": `${siteUrl}/services/custom-ai`
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "Юридический аутсорсинг + AI",
            "description": "Гибридная модель, в которой юридическая экспертиза усиливается AI-инструментами для рутинных процессов.",
            "url": `${siteUrl}/services/outsourcing-ai`
          }
        }
      ]
    }
  };

  // Website Schema
  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    "url": siteUrl,
    "name": "Legal AI PRO",
    "description": "Автоматизация юридической работы на базе искусственного интеллекта",
    "publisher": {
      "@id": `${siteUrl}/#organization`
    },
    "inLanguage": "ru-RU"
  };

  // Breadcrumb Schema
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Главная",
        "item": siteUrl
      },
      {
        "@type": "ListItem",
        "position": 2,
        "name": "Преимущества",
        "item": `${siteUrl}/#features`
      },
      {
        "@type": "ListItem",
        "position": 3,
        "name": "Услуги",
        "item": `${siteUrl}/#services`
      },
      {
        "@type": "ListItem",
        "position": 4,
        "name": "Калькулятор ROI",
        "item": `${siteUrl}/#calculator`
      },
      {
        "@type": "ListItem",
        "position": 5,
        "name": "FAQ",
        "item": `${siteUrl}/#faq`
      }
    ]
  };

  // Person Schema - основатель (обобщенно, без фото)
  const personSchema = {
    "@context": "https://schema.org",
    "@type": "Person",
    "name": "Андрей Попов",
    "jobTitle": "Основатель и CEO Legal AI PRO",
    "description": "Юрист-разработчик с 20+ годами опыта. CLO в крупных агрохолдингах и банках. Более 200 процедур банкротства. Разработчик AI-систем на Python, TypeScript и JavaScript.",
    "knowsAbout": [
      "Юриспруденция",
      "Искусственный интеллект",
      "Machine Learning",
      "Python",
      "TypeScript",
      "Legal Tech",
      "Договорное право",
      "Корпоративное право",
      "Банкротство",
      "M&A",
      "Земельное право"
    ],
    "alumniOf": {
      "@type": "EducationalOrganization",
      "name": "Юридическое образование"
    },
    "worksFor": {
      "@id": `${siteUrl}/#organization`
    },
    "email": "a.popov.gv@gmail.com",
    "telephone": "+7-909-233-09-09"
  };

  // Combine all schemas using @graph
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      organizationSchema,
      serviceSchema,
      websiteSchema,
      breadcrumbSchema,
      personSchema
    ]
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(structuredData, null, 0) // minified
      }}
    />
  );
}
