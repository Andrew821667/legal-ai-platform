import { EXTERNAL_LINKS } from "@/lib/links";
import {
  LEGAL_BRAND,
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE_HREF,
  LEGAL_OPERATOR_NAME,
  LEGAL_SITE_URL,
} from "@/lib/legalProfile";

interface StructuredDataProps {
  siteUrl?: string;
}

export default function StructuredData({ siteUrl = LEGAL_SITE_URL }: StructuredDataProps) {
  const automationOffers = [
    {
      name: "Автоматизация договорной работы",
      description: "AI-анализ договоров, выявление рисков, чек-листы, согласование правок и контроль качества.",
      url: `${siteUrl}/services/contracts-ai`,
    },
    {
      name: "Автоматизация судебной работы",
      description: "Подготовка материалов, структурирование фактов, сбор позиции и контроль событий по делам.",
      url: `${siteUrl}/services/litigation-ai`,
    },
    {
      name: "Автоматизация комплаенса",
      description: "Мониторинг изменений, контроль внутренних правил и сопровождение регулярных проверок.",
      url: `${siteUrl}/services/compliance-ai`,
    },
    {
      name: "Корпоративное право и M&A",
      description: "Ускорение due diligence, анализ корпоративных документов и выявление существенных рисков.",
      url: `${siteUrl}/services/corporate-ma-ai`,
    },
    {
      name: "Юридическая аналитика",
      description: "Риск-дашборды, KPI юридической функции и управленческая аналитика на данных компании.",
      url: `${siteUrl}/services/legal-analytics-ai`,
    },
  ];

  const navigationItems = [
    { name: "Главная", url: siteUrl },
    { name: "Для юристов", url: `${siteUrl}/for-lawyers` },
    { name: "Для бизнеса", url: `${siteUrl}/for-business` },
    { name: "Услуги", url: `${siteUrl}/services` },
    { name: "Решения", url: `${siteUrl}/solutions` },
    { name: "Практические руководства", url: `${siteUrl}/guides` },
    { name: "Сценарии внедрения", url: `${siteUrl}/cases` },
    { name: "Инженерная практика", url: `${siteUrl}/services/custom-ai` },
    { name: "Работа с регионами", url: `${siteUrl}/regions` },
  ];

  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: LEGAL_BRAND,
    url: siteUrl,
    description:
      "Платформа с основной практикой автоматизации юридической функции и отдельными юридической и инженерной практиками.",
    logo: `${siteUrl}/icon.svg`,
    image: `${siteUrl}/opengraph-image`,
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    knowsAbout: [
      "автоматизация юридической работы",
      "legal tech",
      "AI для юристов",
      "автоматизация договоров",
      "автоматизация судебной работы",
      "комплаенс",
      "юридические услуги по российскому праву",
      "разработка программного обеспечения",
      "CRM, ERP и 1C интеграции",
    ],
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer service",
      telephone: LEGAL_CONTACT_PHONE_HREF,
      email: LEGAL_CONTACT_EMAIL,
      availableLanguage: ["Russian", "English"],
      areaServed: "RU",
    },
    sameAs: [EXTERNAL_LINKS.channel],
    founder: {
      "@id": `${siteUrl}/#founder`,
    },
  };

  const serviceSchema = {
    "@context": "https://schema.org",
    "@type": "ProfessionalService",
    "@id": `${siteUrl}/#service`,
    name: LEGAL_BRAND,
    url: siteUrl,
    image: `${siteUrl}/opengraph-image`,
    serviceType: "Legal operations automation and AI automation for legal teams",
    provider: {
      "@id": `${siteUrl}/#organization`,
    },
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    hasOfferCatalog: {
      "@type": "OfferCatalog",
      name: "Legal AI services",
      itemListElement: automationOffers.map((offer) => ({
        "@type": "Offer",
        url: offer.url,
        itemOffered: {
          "@type": "Service",
          name: offer.name,
          description: offer.description,
          url: offer.url,
          areaServed: "RU",
        },
      })),
    },
  };

  const legalPracticeSchema = {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${siteUrl}/legal-help#practice`,
    name: "Юридическая практика AI Verdict",
    description:
      "Юридические услуги по российскому праву для бизнеса и частных клиентов: консультации, договоры, споры, корпоративные, имущественные и личные вопросы.",
    url: `${siteUrl}/legal-help`,
    serviceType: "Юридические услуги по праву Российской Федерации",
    provider: {
      "@id": `${siteUrl}/#organization`,
    },
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    availableChannel: {
      "@type": "ServiceChannel",
      serviceUrl: `${siteUrl}/legal-help`,
      availableLanguage: "ru-RU",
    },
  };

  const engineeringPracticeSchema = {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${siteUrl}/services/custom-ai#practice`,
    name: "Инженерная практика AI Verdict",
    description:
      "Разработка программ, Telegram-ботов, сайтов, Mini App, внутренних сервисов, AI-модулей и интеграций с корпоративными системами.",
    url: `${siteUrl}/services/custom-ai`,
    serviceType: "Разработка программного обеспечения, AI-сервисов и интеграций",
    provider: {
      "@id": `${siteUrl}/#organization`,
    },
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    availableChannel: {
      "@type": "ServiceChannel",
      serviceUrl: `${siteUrl}/services/custom-ai`,
      availableLanguage: "ru-RU",
    },
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    url: siteUrl,
    name: LEGAL_BRAND,
    description: "Сайт о внедрении AI в юридическую функцию и смежной бизнес-автоматизации.",
    publisher: {
      "@id": `${siteUrl}/#organization`,
    },
    inLanguage: "ru-RU",
  };

  const navigationSchema = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "@id": `${siteUrl}/#site-navigation`,
    name: "Основные разделы AI Verdict",
    itemListElement: navigationItems.map((item, index) => ({
      "@type": "SiteNavigationElement",
      position: index + 1,
      name: item.name,
      url: item.url,
    })),
  };

  const personSchema = {
    "@context": "https://schema.org",
    "@type": "Person",
    "@id": `${siteUrl}/#founder`,
    name: LEGAL_OPERATOR_NAME,
    jobTitle: `Основатель и ответственный за продукт ${LEGAL_BRAND}`,
    description:
      "Специалист по автоматизации юридической функции, AI-сценариям и прикладной разработке рабочих контуров.",
    url: `${siteUrl}/team`,
    worksFor: {
      "@id": `${siteUrl}/#organization`,
    },
    email: LEGAL_CONTACT_EMAIL,
    telephone: LEGAL_CONTACT_PHONE_HREF,
  };

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      organizationSchema,
      serviceSchema,
      legalPracticeSchema,
      engineeringPracticeSchema,
      websiteSchema,
      navigationSchema,
      personSchema,
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(structuredData),
      }}
    />
  );
}
