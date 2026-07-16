import type { Metadata } from "next";
import Link from "next/link";

import LegalHelpForm from "@/components/LegalHelpForm";
import { createPageMetadata } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридические услуги для бизнеса",
  description: "Договоры, претензии, корпоративные вопросы, трудовые отношения, налоги, комплаенс, недвижимость, IT и данные для компаний и предпринимателей.",
  path: "/legal-help/business",
});

const items = [
  "Договоры, сделки и переговоры",
  "Претензионная и судебная работа",
  "Корпоративные процедуры и сопровождение сделок",
  "Трудовые отношения и внутренние документы",
  "Налоговые вопросы и комплаенс",
  "Недвижимость, земля и имущественные риски",
  "IT, персональные данные и интеллектуальная собственность",
  "Постоянное юридическое сопровождение",
];

export default function BusinessLegalHelpPage() {
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <section className="border-b border-slate-800">
        <div className="mx-auto max-w-6xl px-4 pb-14 pt-28 sm:px-6 lg:px-8">
          <Link href="/legal-help" className="text-sm text-amber-300 hover:text-amber-200">Юридическая помощь</Link>
          <h1 className="mt-4 text-4xl font-semibold text-white md:text-5xl">Юридические услуги для бизнеса</h1>
          <p className="mt-5 max-w-3xl text-lg text-slate-300">Помогаем компаниям и предпринимателям решать текущие правовые задачи и сопровождать проекты, сделки и споры.</p>
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Основные направления</h2>
        <ul className="mt-6 grid gap-4 md:grid-cols-2">
          {items.map((item) => <li key={item} className="rounded-lg border border-slate-800 bg-slate-800/60 p-5 text-slate-200">{item}</li>)}
        </ul>
      </section>
      <LegalHelpForm sourceContext="web_legal_help_business" initialClientType="company" />
    </main>
  );
}
