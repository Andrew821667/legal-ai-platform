import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Contract_AI_System",
  description:
    "Флагманский продукт Legal AI PRO для проверки договоров: риски, рекомендации по правкам, контроль согласований и аудит юридических решений.",
  alternates: { canonical: "/contract-ai-system" },
};

const valuePoints = [
  {
    title: "Скорость первичной проверки",
    details: "Система за минуты формирует первичный риск-профиль договора и подсвечивает спорные зоны.",
  },
  {
    title: "Предсказуемость качества",
    details: "Единая логика комментариев снижает разрыв между юристами и сокращает число возвратов на доработку.",
  },
  {
    title: "Контроль рисков",
    details: "Выявляются условия по ответственности, срокам, штрафам, расторжению и обязательствам сторон.",
  },
];

const taskTracks = [
  {
    title: "Что решаем для юристов",
    href: "/for-lawyers",
    items: [
      "Ускоряем первичный анализ договора",
      "Упорядочиваем согласование правок",
      "Снижаем рутину на повторяющихся договорах",
    ],
  },
  {
    title: "Что решаем для бизнеса",
    href: "/for-business",
    items: [
      "Сокращаем цикл согласования сделки",
      "Делаем риски прозрачными для руководителей",
      "Стабилизируем SLA юридической функции",
    ],
  },
];

const demoSteps = [
  "Передаете 5-10 типовых договоров и контекст процесса согласования.",
  "Получаете анализ рисков и примеры юридических комментариев/правок.",
  "Сверяем эффект на KPI и фиксируем сценарий пилотного внедрения.",
];

const integrationPoints = [
  "API-контур в рамках текущего ядра платформы",
  "Журнал решений и ручной контроль юриста",
  "Поэтапное расширение на соседние legal-процессы",
  "Поддержка внутренних регламентов и матриц ответственности",
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
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-3">
            <Link
              href="/content-cases"
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-slate-500 transition-colors text-center"
            >
              Узнать на кейсах
            </Link>
            <a
              href="https://t.me/legal_ai_helper_new_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors text-center"
            >
              Проверить договор
            </a>
            <Link
              href="/solutions"
              className="rounded-lg border border-sky-500/60 px-5 py-3 font-semibold text-sky-200 hover:border-sky-300 transition-colors text-center"
            >
              Внедрить решение
            </Link>
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Ценность продукта</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {valuePoints.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h3 className="text-lg font-semibold text-amber-300">{item.title}</h3>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.details}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Ключевые сценарии применения</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {taskTracks.map((track) => (
              <article key={track.title} className="rounded-xl border border-slate-800 bg-slate-950/60 p-6">
                <h3 className="text-xl font-semibold text-amber-300">{track.title}</h3>
                <ul className="mt-3 space-y-2 text-sm text-slate-300 leading-relaxed">
                  {track.items.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
                <Link href={track.href} className="mt-5 inline-flex font-semibold text-sky-300 hover:text-sky-200">
                  Открыть подробный маршрут →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="demo" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Демо и пилот</h2>
        <p className="mt-4 max-w-3xl text-slate-300">
          Для старта не нужна тяжелая интеграция: сначала подтверждаем прикладной эффект на ограниченном наборе
          документов и только потом масштабируем в рабочий контур.
        </p>
        <ol className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {demoSteps.map((step) => (
            <li key={step} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-sm text-slate-200">
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section id="integrations" className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Интеграции и контроль</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {integrationPoints.map((item) => (
              <article key={item} className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 text-slate-200">
                {item}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="rounded-2xl border border-amber-500/35 bg-amber-500/10 p-7">
          <h2 className="text-2xl font-semibold text-white">Следующий шаг</h2>
          <p className="mt-3 max-w-3xl text-slate-200">
            Если хотите разобрать ваш договорный процесс и проверить, где AI даст максимальный эффект, передайте кейс в
            Ассистент Legal AI Pro. Получите понятный формат пилота без лишней архитектурной сложности.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href="https://t.me/legal_ai_helper_new_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
            >
              Передать кейс
            </a>
            <Link
              href="/solutions"
              className="rounded-lg border border-slate-600 px-5 py-3 font-semibold text-slate-100 hover:border-amber-300 hover:text-amber-200 transition-colors"
            >
              Посмотреть roadmap внедрения
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
