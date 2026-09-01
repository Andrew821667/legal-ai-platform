import { Scale, Bot, Workflow, ShieldCheck } from "lucide-react";
import Link from "next/link";
import HeroBackdrop from "@/components/HeroBackdrop";
import { EXTERNAL_LINKS } from "@/lib/links";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_OPERATOR_NAME,
  LEGAL_OPERATOR_STATUS,
} from "@/lib/legalProfile";

const pillars = [
  {
    icon: Scale,
    title: "Юридический контекст",
    description:
      "Разбираем сам процесс: документы, сроки, согласования, риски и точки ручного контроля.",
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

const reviewPrinciples = [
  "Отделяем возможности технологии от подтвержденного результата конкретного пилота.",
  "Юридические утверждения проверяем по применимому праву РФ и указываем дату содержательного обновления.",
  "Не публикуем проценты эффективности, отзывы и истории клиентов без проверяемого основания и разрешения.",
  "Для AI-выводов требуем источник, ручную проверку и понятный маршрут действий при неопределенности.",
];

export default function AboutTeam() {
  return (
    <section id="about" className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      <div className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="collaboration" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-32 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
              О команде
            </h1>
            <p className="text-xl text-slate-200 max-w-3xl mx-auto">
              Мы строим AI-сценарии для юридической функции как инженерный продукт:
              от маршрута заявки и договорного потока до контроля рисков и внутренних регламентов.
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-14 sm:px-6 lg:px-8">
        <div className="mb-12 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-amber-300">
            Ответственный за продукт и материалы
          </p>
          <h2 className="mt-3 text-3xl font-semibold text-white">{LEGAL_OPERATOR_NAME}</h2>
          <p className="mt-2 text-slate-300">
            Основатель AI Verdict, {LEGAL_OPERATOR_STATUS}, юрист с более чем 20-летней практикой и разработчик
            прикладных AI-систем. Отвечает за продуктовую концепцию, методологию внедрения и редакционную проверку
            практических материалов.
          </p>
          <p className="mt-4 text-sm text-slate-400">
            Связаться по вопросам продукта и содержания: {" "}
            <a className="text-amber-300 hover:text-amber-200" href={`mailto:${LEGAL_CONTACT_EMAIL}`}>
              {LEGAL_CONTACT_EMAIL}
            </a>
          </p>
          <p className="mt-3 text-xs leading-relaxed text-slate-400">
            AI Verdict не заменяет индивидуальную юридическую консультацию. Материалы сайта описывают
            процессы автоматизации и требуют проверки применительно к фактам конкретной задачи.
          </p>
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <a
              className="font-semibold text-sky-300 hover:text-sky-200"
              href={EXTERNAL_LINKS.githubProfile}
              target="_blank"
              rel="noopener noreferrer"
            >
              Профиль разработчика на GitHub ↗
            </a>
            <a
              className="font-semibold text-sky-300 hover:text-sky-200"
              href={EXTERNAL_LINKS.githubPlatform}
              target="_blank"
              rel="noopener noreferrer"
            >
              Публичный репозиторий AI Verdict ↗
            </a>
          </div>
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
                  className="rounded-lg border border-slate-600 bg-slate-800/60 px-4 py-2 text-sm text-slate-200"
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

        <section className="mt-10 rounded-2xl border border-sky-500/25 bg-sky-500/10 p-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-sky-300">Редакционная ответственность</p>
          <h2 className="mt-3 text-2xl font-semibold text-white">Как проверяются материалы AI Verdict</h2>
          <ul className="mt-5 grid gap-4 md:grid-cols-2">
            {reviewPrinciples.map((item) => (
              <li key={item} className="rounded-xl border border-slate-700 bg-slate-950/50 p-5 text-sm leading-6 text-slate-300">
                {item}
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-wrap gap-5">
            <Link href="/cases" className="font-semibold text-amber-300 hover:text-amber-200">
              Сценарии и методика измерения →
            </Link>
            <Link href="/guides" className="font-semibold text-sky-300 hover:text-sky-200">
              Практические руководства →
            </Link>
            <Link href="/ai-policy" className="font-semibold text-slate-200 hover:text-white">
              Политика использования AI →
            </Link>
          </div>
        </section>
      </div>
    </section>
  );
}
