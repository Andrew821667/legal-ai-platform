import type { Metadata } from "next";
import AboutTeam from "@/components/AboutTeam";
import { LEGAL_OPERATOR_NAME } from "@/lib/legalProfile";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "О команде",
  description:
    "Основатель AI Verdict, ответственность за продукт и материалы, а также подход к автоматизации юридической функции.",
  path: "/team",
  type: "profile",
});

export default function TeamPage() {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    "@id": `${SEO_SITE_URL}/team#profile`,
    url: `${SEO_SITE_URL}/team`,
    name: `Команда и ответственный за материалы AI Verdict`,
    dateModified: "2026-08-13",
    inLanguage: "ru-RU",
    mainEntity: {
      "@type": "Person",
      "@id": `${SEO_SITE_URL}/#founder`,
      name: LEGAL_OPERATOR_NAME,
      jobTitle: "Основатель и ответственный за продукт AI Verdict",
      worksFor: { "@id": `${SEO_SITE_URL}/#organization` },
    },
  };

  return (
    <main className="min-h-screen bg-slate-800">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
      <AboutTeam />
    </main>
  );
}
