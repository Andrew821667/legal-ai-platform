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
    { name: "ИИ в юридической сфере", url: `${siteUrl}/legal-ai` },
    { name: "Для юристов", url: `${siteUrl}/for-lawyers` },
    { name: "Для бизнеса", url: `${siteUrl}/for-business` },
    { name: "Услуги", url: `${siteUrl}/services` },
    { name: "Юридическая практика", url: `${siteUrl}/legal-help` },
    { name: "Инженерная практика", url: `${siteUrl}/engineering` },
    { name: "Решения", url: `${siteUrl}/solutions` },
    { name: "Комментарии законодательства об ИИ", url: `${siteUrl}/ai-law` },
    { name: "Практические руководства", url: `${siteUrl}/guides` },
    { name: "Сценарии внедрения", url: `${siteUrl}/cases` },
    { name: "Работа с регионами", url: `${siteUrl}/regions` },
  ];

  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: LEGAL_BRAND,
    url: siteUrl,
    description:
      "AI Verdict автоматизирует юридическую функцию, оказывает юридическую помощь и разрабатывает прикладные программные системы.",
    logo: `${siteUrl}/icon.svg`,
    image: `${siteUrl}/opengraph-image`,
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    knowsAbout: [
      "искусственный интеллект в юридической сфере",
      "искусственный интеллект в юриспруденции",
      "юридический ИИ",
      "Legal AI",
      "автоматизация юридической работы",
      "legal tech",
      "AI для юристов",
      "ИИ для юридического отдела",
      "правовой поиск с помощью ИИ",
      "анализ судебной практики с помощью ИИ",
      "промпты для юристов",
      "ИИ для процессуальных документов",
      "автоматизация договоров",
      "автоматизация судебной работы",
      "ИИ в комплаенсе",
      "ИИ в корпоративном праве",
      "KPI и ROI Legal AI",
      "LegalTech и LawTech",
      "юридический ИИ-помощник",
      "юридический AI-чат-бот",
      "RAG для юристов",
      "AI-агенты для юристов",
      "ИИ для юридических фирм и адвокатов",
      "ИИ в отраслях права",
      "правовое регулирование искусственного интеллекта",
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
    sameAs: [EXTERNAL_LINKS.channel, EXTERNAL_LINKS.githubPlatform],
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
    "@id": `${siteUrl}/engineering#practice`,
    name: "Инженерная практика AI Verdict",
    description:
      "Разработка программ, Telegram-ботов, сайтов, Mini App, внутренних сервисов, AI-модулей и интеграций с корпоративными системами.",
    url: `${siteUrl}/engineering`,
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
      serviceUrl: `${siteUrl}/engineering`,
      availableLanguage: "ru-RU",
    },
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    url: siteUrl,
    name: LEGAL_BRAND,
    description: "Сайт юридической и инженерной практик AI Verdict и их совместных проектов по автоматизации юридической функции.",
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
    jobTitle: `Юрист, разработчик AI-систем и основатель ${LEGAL_BRAND}`,
    description:
      "Юрист с более чем 20-летней практикой, специалист по автоматизации юридической функции, Legal AI и прикладной разработке рабочих контуров.",
    url: `${siteUrl}/team`,
    sameAs: [EXTERNAL_LINKS.githubProfile],
    knowsAbout: [
      "юридическая практика",
      "автоматизация юридической функции",
      "Legal AI",
      "анализ договоров с помощью ИИ",
      "разработка прикладных AI-систем",
    ],
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
