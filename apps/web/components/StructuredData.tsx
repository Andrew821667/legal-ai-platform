interface StructuredDataProps {
  siteUrl?: string;
}

export default function StructuredData({ siteUrl = "https://legalaipro.ru" }: StructuredDataProps) {
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: "Legal AI PRO",
    url: siteUrl,
    description:
      "Команда, которая помогает юридическим функциям внедрять AI-сценарии для заявок, договорной работы, комплаенса и типовых процессов.",
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer service",
      telephone: "+7-909-233-09-09",
      email: "a.popov.gv@gmail.com",
      availableLanguage: ["Russian", "English"],
      areaServed: "RU",
    },
    sameAs: ["https://t.me/legal_ai_pro"],
  };

  const serviceSchema = {
    "@context": "https://schema.org",
    "@type": "ProfessionalService",
    "@id": `${siteUrl}/#service`,
    name: "Legal AI PRO",
    serviceType: "AI automation for legal operations",
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
      itemListElement: [
        "Автоматизация договорной работы",
        "Автоматизация судебной работы",
        "Комплаенс и контроль изменений",
        "Юридическая аналитика",
        "Кастомные AI-решения",
      ].map((name) => ({
        "@type": "Offer",
        itemOffered: {
          "@type": "Service",
          name,
        },
      })),
    },
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    url: siteUrl,
    name: "Legal AI PRO",
    description: "Сайт о внедрении AI в юридическую функцию.",
    publisher: {
      "@id": `${siteUrl}/#organization`,
    },
    inLanguage: "ru-RU",
  };

  const personSchema = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: "Андрей Попов",
    jobTitle: "Основатель Legal AI PRO",
    description:
      "Специалист по автоматизации юридической функции и внедрению AI-сценариев в рабочие процессы.",
    worksFor: {
      "@id": `${siteUrl}/#organization`,
    },
    email: "a.popov.gv@gmail.com",
    telephone: "+7-909-233-09-09",
  };

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [organizationSchema, serviceSchema, websiteSchema, personSchema],
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
