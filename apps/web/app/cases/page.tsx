import type { Metadata } from "next";
import CaseStudies from "@/components/CaseStudies";
import { LEGAL_OPERATOR_NAME } from "@/lib/legalProfile";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "Кейсы и сценарии внедрения Legal AI",
  description:
    "Сценарии внедрения Legal AI: договоры, судебная работа и due diligence. Методика пилота, метрики качества, ROI и переход к подтвержденному кейсу.",
  path: "/cases",
  type: "article",
});

export default function CasesPage() {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "@id": `${SEO_SITE_URL}/cases#page`,
    url: `${SEO_SITE_URL}/cases`,
    name: "Кейсы и сценарии внедрения Legal AI",
    description: "Проектные модели и методика подтверждения результата внедрения Legal AI.",
    dateModified: "2026-08-13",
    inLanguage: "ru-RU",
    author: {
      "@type": "Person",
      "@id": `${SEO_SITE_URL}/#founder`,
      name: LEGAL_OPERATOR_NAME,
      url: `${SEO_SITE_URL}/team`,
    },
    isPartOf: { "@id": `${SEO_SITE_URL}/#website` },
    about: [
      { "@type": "Thing", name: "внедрение Legal AI" },
      { "@type": "Thing", name: "автоматизация договоров" },
      { "@type": "Thing", name: "оценка пилота Legal AI" },
    ],
  };

  return (
    <main className="min-h-screen bg-slate-800">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
      <CaseStudies />
    </main>
  );
}
