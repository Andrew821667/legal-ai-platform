import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Для бизнеса",
  description:
    "Сценарии для руководителей и операционных команд: управляемая юридическая функция, SLA, снижение рисков и ускорение согласований.",
  alternates: { canonical: "/for-business" },
};

const outcomes = [
  "Сокращение срока согласования договоров и приложений",
  "Прозрачный контроль юридических рисков по сделкам",
  "Управляемая загрузка юридической команды и SLA",
  "Снижение зависимости от ручной рутины и повторяющихся задач",
];

const audiences = [
  {
    title: "Собственник / CEO",
    details: "Контроль юридических рисков и сроков в привязке к выручке и операционным целям.",
  },
  {
    title: "COO / операционный блок",
    details: "Ускорение договорных циклов и снижение потерь на межфункциональных согласованиях.",
  },
  {
    title: "Руководитель юрдепартамента",
    details: "Стабильное качество юридических решений и прогнозируемая загрузка команды.",
  },
];

export default function ForBusinessPage() {
  return (
    <main className="bg-slate-950 text-slate-100 min-h-screen">
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-sky-500/40 bg-sky-500/10 px-4 py-1 text-sm text-sky-300">
            Для бизнеса и руководителей
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">
            Юридическая функция как управляемая часть бизнеса, а не узкое место
          </h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Строим контур, в котором юридические задачи решаются быстрее, прозрачнее и с контролем качества, а команда
            концентрируется на сложных вопросах вместо потока типовой рутины.
          </p>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Ключевой эффект</h2>
        <ul className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {outcomes.map((outcome) => (
            <li key={outcome} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
              {outcome}
            </li>
          ))}
        </ul>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Кому полезно в первую очередь</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            {audiences.map((audience) => (
              <article key={audience.title} className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
                <h3 className="font-semibold text-amber-300">{audience.title}</h3>
                <p className="mt-2 text-sm text-slate-300 leading-relaxed">{audience.details}</p>
              </article>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/contract-ai-system"
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
            >
              Посмотреть Contract_AI_System
            </Link>
            <a
              href="https://t.me/legal_ai_helper_new_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-sky-400 hover:text-sky-300 transition-colors"
            >
              Обсудить внедрение
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
