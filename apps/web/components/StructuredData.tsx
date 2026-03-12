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
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: LEGAL_BRAND,
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
      telephone: LEGAL_CONTACT_PHONE_HREF,
      email: LEGAL_CONTACT_EMAIL,
      availableLanguage: ["Russian", "English"],
      areaServed: "RU",
    },
    sameAs: [EXTERNAL_LINKS.channel],
  };

  const serviceSchema = {
    "@context": "https://schema.org",
    "@type": "ProfessionalService",
    "@id": `${siteUrl}/#service`,
    name: LEGAL_BRAND,
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
    name: LEGAL_BRAND,
    description: "Сайт о внедрении AI в юридическую функцию.",
    publisher: {
      "@id": `${siteUrl}/#organization`,
    },
    inLanguage: "ru-RU",
  };

  const personSchema = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: LEGAL_OPERATOR_NAME,
    jobTitle: `Основатель ${LEGAL_BRAND}`,
    description:
      "Специалист по автоматизации юридической функции и внедрению AI-сценариев в рабочие процессы.",
    worksFor: {
      "@id": `${siteUrl}/#organization`,
    },
    email: LEGAL_CONTACT_EMAIL,
    telephone: LEGAL_CONTACT_PHONE_HREF,
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
