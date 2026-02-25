import type { Metadata } from "next";
import CaseStudies from "@/components/CaseStudies";

export const metadata: Metadata = {
  title: "Кейсы внедрения Legal AI",
  description:
    "Реальные кейсы внедрения AI в юридической работе: договоры, судебные процессы и Due Diligence с измеримым результатом.",
  alternates: {
    canonical: "/cases",
  },
  openGraph: {
    title: "Кейсы внедрения Legal AI | Legal AI PRO",
    description:
      "Примеры проектов с измеримыми результатами в автоматизации юридических процессов.",
    url: "/cases",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Кейсы внедрения Legal AI | Legal AI PRO",
    description:
      "Примеры проектов с измеримыми результатами в автоматизации юридических процессов.",
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
