import type { Metadata } from "next";
import CaseStudies from "@/components/CaseStudies";

export const metadata: Metadata = {
  title: "Сценарии внедрения Legal AI",
  description:
    "Типовые сценарии внедрения AI в юридической функции: договоры, судебный контур и обзор массивов документов.",
  alternates: {
    canonical: "/cases",
  },
  openGraph: {
    title: "Сценарии внедрения Legal AI | Legal AI PRO",
    description:
      "Типовые паттерны внедрения AI в юридической работе и то, где они обычно дают эффект.",
    url: "/cases",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Сценарии внедрения Legal AI | Legal AI PRO",
    description:
      "Типовые паттерны внедрения AI в юридической работе и то, где они обычно дают эффект.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function CasesPage() {
  return (
    <main className="min-h-screen bg-slate-900">
      <CaseStudies />
    </main>
  );
}
