"use client";

import { Scale, Bot, Workflow, ShieldCheck } from "lucide-react";

const pillars = [
  {
    icon: Scale,
    title: "Юридический контекст",
    description:
      "Смотрим не только на модель, но и на сам процесс: документы, сроки, согласования, риски и точки ручного контроля.",
  },
  {
    icon: Bot,
    title: "Собственная разработка",
    description:
      "Сами собираем backend, ботовые сценарии, контуры публикации и интеграции. Это позволяет быстрее менять продукт и не зависеть от шаблонных коробок.",
  },
  {
    icon: Workflow,
    title: "Внедрение по шагам",
    description:
      "Начинаем с пилота на одном процессе, проверяем эффект, затем масштабируем только те сценарии, которые реально работают в вашей среде.",
  },
  {
    icon: ShieldCheck,
    title: "Контроль данных и ответственности",
    description:
      "До запуска разбираем, где персональные данные, коммерческая тайна, кто принимает финальное решение и какие ограничения есть у инфраструктуры.",
  },
];

const workflow = [
  "Разобрать текущий маршрут задачи и узкие места.",
  "Определить, что можно автоматизировать без потери контроля.",
  "Собрать пилот на реальных материалах и критериях качества.",
  "Настроить правила использования, права доступа и ручную проверку.",
];

const stack = [
  "Python / FastAPI",
  "PostgreSQL",
  "Telegram Bot API",
  "Next.js / TypeScript",
  "RAG и внутренняя база знаний",
  "Интеграции с CRM, ЭДО и внутренними системами",
];

export default function AboutTeam() {
  return (
    <section id="about" className="py-20 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            О команде
          </h1>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto">
            Мы строим AI-сценарии для юридической функции как инженерный продукт:
            от маршрута заявки и договорного потока до контроля рисков и внутренних регламентов.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          {pillars.map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-white/15 bg-white/10 backdrop-blur-sm p-7"
            >
              <div className="inline-flex rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 mb-4">
                <item.icon className="w-6 h-6 text-amber-400" />
              </div>
              <h2 className="text-2xl font-semibold text-white mb-3">{item.title}</h2>
              <p className="text-slate-300 leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="rounded-2xl border border-white/15 bg-white/10 backdrop-blur-sm p-8">
            <h2 className="text-2xl font-semibold text-white mb-5">
              Как мы подходим к проекту
            </h2>
            <ol className="space-y-4">
              {workflow.map((item, index) => (
                <li key={item} className="flex gap-4">
                  <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-amber-500 text-slate-950 font-semibold text-sm">
                    {index + 1}
                  </div>
                  <p className="text-slate-300 leading-relaxed">{item}</p>
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded-2xl border border-white/15 bg-white/10 backdrop-blur-sm p-8">
            <h2 className="text-2xl font-semibold text-white mb-5">
              Что обычно входит в стек
            </h2>
            <div className="flex flex-wrap gap-3">
              {stack.map((item) => (
                <span
                  key={item}
                  className="rounded-lg border border-slate-600 bg-slate-900/60 px-4 py-2 text-sm text-slate-200"
                >
                  {item}
                </span>
              ))}
            </div>
            <p className="text-slate-400 text-sm mt-6 leading-relaxed">
              Конкретный стек и модель выбираем под задачу, ограничения по данным,
              требования к локализации и бюджет пилота.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
