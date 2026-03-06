import type { Metadata } from "next";
import { ROUTES } from "@/lib/links";
import CtaFrameworkPanel from "@/components/CtaFrameworkPanel";

export const metadata: Metadata = {
  title: "Для юристов",
  description:
    "Практические сценарии автоматизации юридической работы: договоры, претензии, контроль рисков, юридические шаблоны и legal ops.",
  alternates: { canonical: "/for-lawyers" },
};

const tracks = [
  {
    title: "Договорный поток",
    description: "Предпроверка рисков, чек-листы, согласование правок и единый стандарт комментариев.",
  },
  {
    title: "Претензионная и судебная подготовка",
    description: "Сбор позиции, структурирование фактов, подготовка проектной документации.",
  },
  {
    title: "Legal ops",
    description: "SLA, шаблоны, маршрутизация задач, контроль нагрузки и качество юридических ответов.",
  },
];

export default function ForLawyersPage() {
  return (
    <main className="bg-slate-950 text-slate-100 min-h-screen">
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Для юридических команд
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">
            Автоматизация, которая помогает юристу работать быстрее и точнее
          </h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Фокусируемся на повторяемых задачах, где нужна скорость и контроль рисков: договоры, согласования,
            претензионные контуры, шаблоны и контроль качества юридической коммуникации.
          </p>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {tracks.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h2 className="text-xl font-semibold text-amber-300">{item.title}</h2>
              <p className="mt-3 text-slate-300 text-sm leading-relaxed">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Как запускаем внедрение</h2>
          <ol className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <li className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
              <p className="text-amber-300 font-semibold">1. Диагностика</p>
              <p className="mt-2 text-sm text-slate-300">Фиксируем процесс, риски, объем рутины и точки экономии времени.</p>
            </li>
            <li className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
              <p className="text-amber-300 font-semibold">2. Пилот</p>
              <p className="mt-2 text-sm text-slate-300">Запускаем ограниченный сценарий и измеряем фактический эффект на KPI.</p>
            </li>
            <li className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
              <p className="text-amber-300 font-semibold">3. Масштабирование</p>
              <p className="mt-2 text-sm text-slate-300">Закрепляем правила и переносим подход на соседние юридические процессы.</p>
            </li>
          </ol>
          <div className="mt-8">
            <CtaFrameworkPanel
              leadStart="web_for_lawyers"
              miniAppHref={ROUTES.miniAppTools}
              title="Единый маршрут для юристов: Узнать -> Проверить -> Внедрить"
            />
          </div>
        </div>
      </section>
    </main>
  );
}
