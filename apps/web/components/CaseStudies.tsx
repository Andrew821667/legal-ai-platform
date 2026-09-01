import HeroBackdrop from "@/components/HeroBackdrop";
import Link from "next/link";

const evidenceSteps = [
  {
    title: "Исходная линия",
    text: "До пилота фиксируем объем задач, медианное время полного цикла, возвраты и критичные ошибки.",
  },
  {
    title: "Контрольный набор",
    text: "Ответственный специалист заранее размечает примеры и определяет допустимые и критичные расхождения.",
  },
  {
    title: "Проверка на новых данных",
    text: "Результат оценивается не на демонстрации, а на документах и задачах, которых система раньше не видела.",
  },
  {
    title: "Решение о масштабе",
    text: "Процесс расширяется, только если эффект воспроизводится, а цена контроля и ошибок остается приемлемой.",
  },
];

const cases = [
  {
    title: "Поток договоров и согласований",
    href: "/services/contracts-ai",
    problem: [
      "Много однотипных договоров и повторяющихся комментариев.",
      "Юристы тратят время на первый проход и ручную сверку шаблонов.",
      "Бизнес долго ждет обратную связь по документу.",
    ],
    solution: [
      "Выделить типовые сценарии и спорные зоны по регламенту компании.",
      "Собрать AI-черновик проверки с подсветкой условий и маршрутом согласования.",
      "Оставить финальное решение и правку за юристом.",
    ],
    result: [
      "Сокращается время на первый проход по документу.",
      "Бизнес быстрее получает обратную связь по типовым формам.",
      "Команда концентрируется на сложных переговорах и нетиповых рисках.",
    ],
    metrics: ["время полного цикла", "критичные пропуски", "ложные замечания", "число возвратов"],
    proofHref: "/contract-ai-system",
    proofLabel: "Посмотреть действующий Contract AI",
  },
  {
    title: "Судебный и претензионный контур",
    href: "/services/litigation-ai",
    problem: [
      "Нужно постоянно отслеживать события, сроки и похожую практику.",
      "Повторяющиеся документы готовятся вручную и долго сверяются.",
      "Руководству сложно видеть общую картину по портфелю споров.",
    ],
    solution: [
      "Настроить сбор событий и статусный мониторинг по делам.",
      "Собирать черновики процессуальных документов и short-list практики.",
      "Собрать основные метрики в одном управленческом отчете.",
    ],
    result: [
      "Становится проще контролировать сроки и статусы.",
      "Уходит часть рутинной подготовки к типовым процессуальным действиям.",
      "Появляется более прозрачная картина судебной нагрузки.",
    ],
    metrics: ["актуальность статусов", "пропущенные сроки", "время подготовки", "ручная сверка"],
    proofHref: null,
    proofLabel: null,
  },
  {
    title: "Due diligence и внутренний обзор массивов документов",
    href: "/services/corporate-ma-ai",
    problem: [
      "Большой массив документов долго разбирается вручную.",
      "Сложно быстро выделить критичные вопросы для следующего этапа проверки.",
      "Руководство получает материалы поздно и в разном формате.",
    ],
    solution: [
      "Сделать предварительную сортировку и группировку документов по типам и рискам.",
      "Собирать структурированный first-pass обзор для команды и руководства.",
      "Дальше включать ручную правовую оценку по выбранным зонам внимания.",
    ],
    result: [
      "Команда быстрее понимает структуру массива и приоритеты проверки.",
      "Руководство получает более понятный обзор на раннем этапе.",
      "Юристы тратят больше времени на анализ, а не на механическую сортировку.",
    ],
    metrics: ["скорость первичного обзора", "точность классификации", "критичные пропуски", "ручная доработка"],
    proofHref: null,
    proofLabel: null,
  },
];

export default function CaseStudies() {
  return (
    <section className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      <div className="relative flex min-h-[560px] items-center overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="home" tone="light" priority />
        <div className="relative mx-auto w-full max-w-6xl px-4 pb-14 pt-24 sm:px-6 sm:py-28 lg:px-8">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-amber-700">Практические модели проекта</p>
            <h1 className="mt-3 text-4xl font-bold text-white md:text-5xl">
              Типовые сценарии внедрения
            </h1>
            <p className="mt-5 text-lg leading-8 text-slate-700">
              Показываем не неподтвержденные проценты, а проверяемые модели: исходную проблему, состав рабочего
              контура, ожидаемый эффект и маршрут к измерению результата на пилоте.
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-14 sm:px-6 lg:px-8">
        <div className="space-y-8">
          {cases.map((item) => (
            <article
              key={item.title}
              className="rounded-2xl border border-white/15 bg-white/10 backdrop-blur-sm p-8"
            >
              <h2 className="text-3xl font-semibold text-white mb-8">{item.title}</h2>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div>
                  <h3 className="text-lg font-semibold text-slate-200 mb-4">Проблема</h3>
                  <ul className="space-y-3 text-slate-300">
                    {item.problem.map((point) => (
                      <li key={point}>• {point}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-amber-300 mb-4">Что меняем</h3>
                  <ul className="space-y-3 text-slate-300">
                    {item.solution.map((point) => (
                      <li key={point}>• {point}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-slate-200 mb-4">Какой эффект ожидаем</h3>
                  <ul className="space-y-3 text-slate-300">
                    {item.result.map((point) => (
                      <li key={point}>• {point}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-7 rounded-xl border border-slate-600 bg-slate-950/50 p-5">
                <h3 className="font-semibold text-sky-300">Что измеряем на пилоте</h3>
                <ul className="mt-4 flex flex-wrap gap-2">
                  {item.metrics.map((metric) => (
                    <li key={metric} className="rounded-full border border-slate-700 px-3 py-1.5 text-sm text-slate-300">
                      {metric}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="mt-8 border-t border-white/15 pt-5">
                <Link href={item.href} className="font-semibold text-amber-300 hover:text-amber-200">
                  Посмотреть состав решения →
                </Link>
                {item.proofHref ? (
                  <Link href={item.proofHref} className="ml-0 mt-3 block font-semibold text-sky-300 hover:text-sky-200 sm:ml-6 sm:mt-0 sm:inline-flex">
                    {item.proofLabel} →
                  </Link>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        <section className="mt-12 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7 md:p-9">
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">Методика доказательства результата</p>
          <h2 className="mt-3 text-3xl font-semibold text-white">Как сценарий становится подтвержденным кейсом</h2>
          <p className="mt-4 max-w-4xl leading-7 text-slate-300">
            Здесь опубликованы проектные модели, а не вымышленные истории клиентов. Именованный кейс, проценты и
            экономический эффект появятся только после измерения на согласованном наборе и разрешения на публикацию.
          </p>
          <ol className="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {evidenceSteps.map((step, index) => (
              <li key={step.title} className="rounded-xl border border-slate-700 bg-slate-950/60 p-5">
                <span className="text-sm font-bold text-amber-300">0{index + 1}</span>
                <h3 className="mt-2 font-semibold text-white">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{step.text}</p>
              </li>
            ))}
          </ol>
          <div className="mt-7 flex flex-wrap gap-4">
            <Link href="/legal-ai/roi" className="font-semibold text-amber-300 hover:text-amber-200">
              Рассчитать ROI пилота →
            </Link>
            <Link href="/guides/legal-ai-implementation" className="font-semibold text-sky-300 hover:text-sky-200">
              Методика запуска Legal AI →
            </Link>
            <Link href="/team" className="font-semibold text-slate-200 hover:text-white">
              Ответственный за материалы →
            </Link>
          </div>
        </section>
      </div>
    </section>
  );
}
