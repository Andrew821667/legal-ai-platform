import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Contract_AI_System",
  description:
    "Флагманский продукт Legal AI PRO для проверки договоров: риски, рекомендации по правкам, контроль согласований и аудит юридических решений.",
  alternates: { canonical: "/contract-ai-system" },
};

const capabilities = [
  {
    title: "Риск-анализ договора",
    details: "Подсветка потенциально рискованных условий: ответственность, сроки, штрафы, порядок расторжения.",
  },
  {
    title: "Юридические комментарии",
    details: "Пояснение логики выявленных рисков и рекомендации по корректным формулировкам.",
  },
  {
    title: "Управляемое согласование",
    details: "Встраивание в текущий процесс согласований с ручным контролем и журналом изменений.",
  },
  {
    title: "Пилот и масштабирование",
    details: "Запуск на ограниченном контуре с измерением эффекта и переносом в рабочий процесс.",
  },
];

export default function ContractAISystemPage() {
  return (
    <main className="bg-slate-950 text-slate-100 min-h-screen">
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-emerald-500/40 bg-emerald-500/10 px-4 py-1 text-sm text-emerald-300">
            Флагманский продукт платформы
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">Contract_AI_System</h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Центральная точка входа в автоматизацию юридической функции: быстрый анализ договоров, выявление рисков,
            рекомендации по правкам и подготовка решений для согласования.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="https://t.me/legal_ai_helper_new_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-amber-500 px-6 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
            >
              Запросить демо
            </a>
            <Link
              href="/solutions"
              className="rounded-lg border border-slate-700 px-6 py-3 font-semibold text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              Сценарии внедрения
            </Link>
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Что система делает на практике</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {capabilities.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h3 className="text-xl font-semibold text-amber-300">{item.title}</h3>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.details}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="demo" className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Демо и пилот</h2>
          <p className="mt-4 max-w-3xl text-slate-300">
            Для старта достаточно 5-10 типовых договоров и описания текущего процесса согласования. Покажем, где система
            экономит время и какие риски фиксирует лучше ручной первичной проверки.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <a
              href="https://t.me/legal_ai_helper_new_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-sky-500 px-5 py-3 font-semibold text-slate-950 hover:bg-sky-400 transition-colors"
            >
              Передать кейс в Ассистент Legal AI Pro
            </a>
            <Link
              href="/for-lawyers"
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-sky-400 hover:text-sky-300 transition-colors"
            >
              Сценарии для юристов
            </Link>
          </div>
        </div>
      </section>

      <section id="integrations" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Интеграционный контур</h2>
        <p className="mt-4 max-w-3xl text-slate-300">
          Встраиваемся в действующий процесс без полного переворота инфраструктуры: API-интеграции, роль человека в
          контроле и поэтапное расширение автоматизации.
        </p>
      </section>
    </main>
  );
}
