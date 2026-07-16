import type { Metadata } from "next";
import Link from "next/link";

import LegalHelpForm from "@/components/LegalHelpForm";
import { createPageMetadata } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридическая помощь частным лицам",
  description: "Помощь по договорам, спорам, недвижимости, трудовым, семейным, наследственным, долговым и другим юридическим вопросам.",
  path: "/legal-help/individuals",
});

const items = [
  "Договоры и сделки",
  "Судебные споры и защита прав",
  "Семейные и наследственные вопросы",
  "Недвижимость, жильё и земля",
  "Трудовые отношения",
  "Долги, взыскание и банкротство",
  "Налоговые и административные вопросы",
  "Другие юридические ситуации",
];

export default function IndividualLegalHelpPage() {
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <section className="border-b border-slate-800">
        <div className="mx-auto max-w-6xl px-4 pb-14 pt-28 sm:px-6 lg:px-8">
          <Link href="/legal-help" className="text-sm text-amber-300 hover:text-amber-200">Юридическая помощь</Link>
          <h1 className="mt-4 text-4xl font-semibold text-white md:text-5xl">Юридическая помощь частным лицам</h1>
          <p className="mt-5 max-w-3xl text-lg text-slate-300">Опишите ситуацию обычными словами. Мы определим, какие сведения нужны, и предложим дальнейший порядок работы.</p>
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">С какими вопросами можно обратиться</h2>
        <ul className="mt-6 grid gap-4 md:grid-cols-2">
          {items.map((item) => <li key={item} className="rounded-lg border border-slate-800 bg-slate-800/60 p-5 text-slate-200">{item}</li>)}
        </ul>
      </section>
      <LegalHelpForm sourceContext="web_legal_help_individuals" initialClientType="individual" />
    </main>
  );
}
