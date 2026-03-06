import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "О платформе",
  description:
    "О платформе Legal AI PRO: подход к внедрению, методология пилота, роль команды и контакты для запуска проекта.",
  alternates: { canonical: "/about" },
};

const principles = [
  "Решаем прикладные задачи юридической функции, а не внедряем AI ради AI.",
  "Начинаем с пилота и прозрачных метрик результата.",
  "Сохраняем управляемость: роль юриста в принятии решений обязательна.",
  "Масштабируем только то, что доказало эффект на практике.",
];

export default function AboutPage() {
  return (
    <main className="bg-slate-950 text-slate-100 min-h-screen">
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            О платформе и подходе
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">Legal AI PRO</h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Строим единую систему, где контент, продукт и внедрение работают вместе: от экспертного контекста и
            проверки договоров до управляемых юридических процессов в компании.
          </p>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Принципы работы</h2>
        <ul className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {principles.map((item) => (
            <li key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40" id="contacts">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Контакты</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <article className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
              <h3 className="font-semibold text-amber-300">Telegram</h3>
              <p className="mt-2 text-sm text-slate-300">
                <a href="https://t.me/legal_ai_helper_new_bot" target="_blank" rel="noopener noreferrer" className="hover:text-amber-300">
                  Ассистент Legal AI Pro
                </a>
              </p>
            </article>
            <article className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
              <h3 className="font-semibold text-amber-300">Канал</h3>
              <p className="mt-2 text-sm text-slate-300">
                <a href="https://t.me/legal_ai_pro" target="_blank" rel="noopener noreferrer" className="hover:text-amber-300">
                  @legal_ai_pro
                </a>
              </p>
            </article>
            <article className="rounded-xl border border-slate-800 bg-slate-950/60 p-5">
              <h3 className="font-semibold text-amber-300">Email</h3>
              <p className="mt-2 text-sm text-slate-300">
                <a href="mailto:a.popov.gv@gmail.com" className="hover:text-amber-300">
                  a.popov.gv@gmail.com
                </a>
              </p>
            </article>
          </div>
        </div>
      </section>
    </main>
  );
}
