import type { Metadata } from "next";
import Link from "next/link";
import { Building2, FileText, Landmark, Scale, ShieldCheck, UserRound } from "lucide-react";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpForm from "@/components/LegalHelpForm";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридическая помощь для бизнеса и частных клиентов",
  description:
    "Юридическая помощь AI Verdict: договоры, споры, корпоративные, трудовые, налоговые, имущественные и другие задачи. Опишите ситуацию и получите предложение по формату работы.",
  path: "/legal-help",
  keywords: ["юридическая помощь", "юридические услуги", "юрист для бизнеса", "консультация юриста"],
});

const areas = [
  { icon: FileText, title: "Договоры и сделки", text: "Проверка, подготовка, переговоры и сопровождение исполнения." },
  { icon: Scale, title: "Претензии и споры", text: "Оценка ситуации, досудебная работа и судебное сопровождение." },
  { icon: Building2, title: "Бизнес и корпоративные вопросы", text: "Корпоративные процедуры, сделки, внутренние документы и сопровождение бизнеса." },
  { icon: Landmark, title: "Недвижимость, земля и долги", text: "Сделки, имущественные споры, взыскание и вопросы банкротства." },
  { icon: ShieldCheck, title: "Налоги, комплаенс, IT и данные", text: "Регуляторные риски, персональные данные, цифровые продукты и интеллектуальная собственность." },
  { icon: UserRound, title: "Личные юридические вопросы", text: "Трудовые, семейные, наследственные, потребительские и другие ситуации." },
];

export default function LegalHelpPage() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: "Юридическая помощь AI Verdict",
    serviceType: "Юридические услуги",
    provider: { "@type": "Organization", name: "AI Verdict", url: SEO_SITE_URL },
    areaServed: "RU",
    url: `${SEO_SITE_URL}/legal-help`,
  };

  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="relative overflow-hidden border-b border-slate-800">
        <HeroBackdrop variant="services" tone="light" />
        <div className="relative mx-auto max-w-7xl px-4 pb-16 pt-28 sm:px-6 lg:px-8">
          <p className="text-sm font-semibold text-amber-300">Юридическое направление AI Verdict</p>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Юридическая помощь для бизнеса и частных клиентов
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-300">
            Мы не только разрабатываем юридические технологии, но и работаем с правом на практике. Опишите задачу,
            ближайший срок и оставьте контакт. Юрист изучит обращение и предложит понятный следующий шаг.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a href="#legal-help-form" className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400">
              Описать задачу
            </a>
            <Link href="/legal-help/business" className="rounded-lg border border-slate-700 px-6 py-3 text-center font-semibold text-slate-200 hover:border-amber-500 hover:text-amber-300">
              Помощь бизнесу
            </Link>
            <Link href="/legal-help/individuals" className="rounded-lg border border-slate-700 px-6 py-3 text-center font-semibold text-slate-200 hover:border-amber-500 hover:text-amber-300">
              Частным клиентам
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-semibold text-white">С какими задачами можно обратиться</h2>
          <p className="mt-3 text-slate-300">Необязательно самостоятельно определять отрасль права. Достаточно описать ситуацию своими словами.</p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {areas.map((area) => (
            <article key={area.title} className="rounded-lg border border-slate-800 bg-slate-800/60 p-6">
              <area.icon className="h-6 w-6 text-amber-300" />
              <h3 className="mt-4 text-lg font-semibold text-white">{area.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">{area.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-3 lg:px-8">
          <div>
            <p className="text-sm font-semibold text-amber-300">1. Обращение</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Вы описываете задачу</h2>
            <p className="mt-3 text-sm text-slate-300">Без регистрации, загрузки документов и сложной анкеты.</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-300">2. Проверка</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Юрист уточняет обстоятельства</h2>
            <p className="mt-3 text-sm text-slate-300">Проверяем сроки, возможность принять задачу и необходимый объём работы.</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-300">3. Условия</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Согласовываем формат и стоимость</h2>
            <p className="mt-3 text-sm text-slate-300">Юридическая работа начинается только после согласования условий.</p>
          </div>
        </div>
      </section>

      <LegalHelpForm sourceContext="web_legal_help" />
    </main>
  );
}
