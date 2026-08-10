import Link from "next/link";
import { Braces, FileCheck2, Workflow } from "lucide-react";

import { ROUTES } from "@/lib/links";

export default function PracticeIntersection() {
  return (
    <section className="border-y border-slate-800 bg-slate-800/40" aria-labelledby="practice-intersection-title">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-16">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold text-amber-300">Архитектура AI Verdict</p>
          <h2 id="practice-intersection-title" className="mt-2 pr-14 text-2xl font-semibold text-white sm:pr-0 md:text-3xl">
            Две практики. Одна ключевая специализация
          </h2>
          <p className="mt-3 text-slate-300">
            Юридическая и инженерная экспертиза работают самостоятельно, а для автоматизации юридической функции
            объединяются в одну проектную команду.
          </p>
        </div>

        <div className="relative mt-9 grid gap-4 lg:grid-cols-[1fr_1.12fr_1fr] lg:items-stretch">
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 hidden h-full w-full lg:block"
            preserveAspectRatio="none"
            viewBox="0 0 1200 300"
          >
            <path d="M350 150 C 430 150, 450 150, 520 150" fill="none" stroke="rgba(217,119,6,.52)" strokeWidth="2" />
            <path d="M850 150 C 770 150, 750 150, 680 150" fill="none" stroke="rgba(71,85,105,.58)" strokeWidth="2" />
            <circle cx="350" cy="150" fill="#d97706" r="5" />
            <circle cx="850" cy="150" fill="#475569" r="5" />
          </svg>

          <article className="relative rounded-2xl border border-amber-500/35 bg-white/90 p-6 shadow-sm">
            <FileCheck2 aria-hidden="true" className="h-7 w-7 text-amber-700" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-wide text-amber-700">Юридическая практика</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Право определяет логику</h3>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Обстоятельства, документы, нормы, риски, контрольные точки и ответственность специалиста.
            </p>
            <Link href={ROUTES.legalHelp} className="mt-5 inline-flex font-semibold text-amber-700 hover:text-amber-600">
              Юридическая помощь →
            </Link>
          </article>

          <article className="relative rounded-2xl border border-amber-500/55 bg-slate-950 p-6 text-white shadow-[0_20px_50px_rgba(15,23,42,0.16)] lg:-my-3 lg:p-8">
            <Workflow aria-hidden="true" className="h-8 w-8 text-amber-400" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-wide text-amber-300">Ключевое пересечение</p>
            <h3 className="mt-2 text-2xl font-semibold">Автоматизация юридической функции</h3>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              Диагностика процесса, юридическая модель, интерфейсы, AI, интеграции и эксплуатация в одном контуре.
            </p>
            <Link href={ROUTES.solutions} className="mt-5 inline-flex font-semibold text-amber-300 hover:text-amber-200">
              Посмотреть решения →
            </Link>
          </article>

          <article className="relative rounded-2xl border border-slate-400/55 bg-white/90 p-6 shadow-sm">
            <Braces aria-hidden="true" className="h-7 w-7 text-slate-700" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-600">Инженерная практика</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">Инженерия превращает её в систему</h3>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Архитектура, боты, сайты, Mini App, AI-модули, интеграции, данные и надежная эксплуатация.
            </p>
            <Link href={ROUTES.engineering} className="mt-5 inline-flex font-semibold text-slate-700 hover:text-amber-700">
              Инженерная практика →
            </Link>
          </article>
        </div>
      </div>
    </section>
  );
}
