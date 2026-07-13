import type { Metadata } from "next";
import CaseStudies from "@/components/CaseStudies";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "Сценарии внедрения Legal AI",
  description:
    "Типовые сценарии внедрения AI в юридической функции: договоры, судебный контур и обзор массивов документов.",
  path: "/cases",
  type: "article",
});

export default function CasesPage() {
  return (
    <main className="min-h-screen bg-slate-800">
      <CaseStudies />
    </main>
  );
}
