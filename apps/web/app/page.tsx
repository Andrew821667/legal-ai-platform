import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES, contractAIEntryHref, contractAIEntryIsExternal, leadBotDeepLink } from "@/lib/links";
import LeadCaptureForm from "@/components/LeadCaptureForm";
import PlatformMap from "@/components/PlatformMap";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = {
  title: "AI Verdict — автоматизация юридических процессов и интеграций",
  description:
    "AI Verdict автоматизирует юридические бизнес-процессы, интегрирует их с системами компании и при необходимости разрабатывает боты, сайты, mini app, AI-модули и внутренние сервисы.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "AI Verdict — автоматизация юридических бизнес-процессов",
    description:
      "AI-сценарии, интеграции, боты, сайты, Mini App и внутренние сервисы вокруг юридической функции и смежных процессов.",
    url: "/",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Verdict — автоматизация юридических бизнес-процессов",
    description:
      "Автоматизируем legal-процессы, интеграции и прикладные решения с AI там, где он действительно нужен.",
  },
};

const roleCards = [
  {
    title: "Юридическая команда",
    description:
      "Договоры, претензии, legal intake, шаблоны, база знаний, контроль сроков и снижение ручной рутины без потери юридической точности.",
    href: ROUTES.forLawyers,
    cta: "Сценарии для юристов",
  },
  {
    title: "Руководитель бизнеса",
    description:
      "Прозрачные сроки, контроль рисков, управляемые согласования, понятная загрузка команды и автоматизация процессов, которые тормозят продажи или операции.",
    href: ROUTES.forBusiness,
    cta: "Сценарии для бизнеса",
  },
  {
    title: "Смежный контур",
    description:
      "Связываем юридические процессы с заявками, статусами, уведомлениями, документами, таблицами, внутренними панелями и повторяющимися действиями между подразделениями.",
    href: "/services/custom-ai",
    cta: "Обсудить автоматизацию",
  },
  {
    title: "IT и интеграции",
    description:
      "Подключаем CRM, ERP, 1C, ЭДО, Google Sheets, базы данных, Telegram, сайты и внутренние сервисы в единый управляемый процесс.",
    href: ROUTES.solutions,
    cta: "Посмотреть архитектуру",
  },
];

const platformLayers = [
  {
    title: "Процесс",
    description: "Фиксируем, где теряются заявки, документы, согласования, статусы, ответственность и время команды.",
  },
  {
    title: "AI-слой",
    description: "Добавляем анализ документов, классификацию запросов, поиск по базе знаний, генерацию черновиков и подсказки человеку.",
  },
  {
    title: "Интерфейсы",
    description: "Делаем Telegram-боты, Mini App, сайты, личные кабинеты, внутренние панели и рабочие экраны под роли пользователей.",
  },
  {
    title: "Интеграции",
    description: "Связываем решение с CRM, ERP, 1C, ЭДО, таблицами, базами данных и существующей инфраструктурой клиента.",
  },
];

const cases = [
  "Юридические процессы: договоры, претензии, legal intake, комплаенс, база знаний, шаблоны",
  "Связанные процессы: заявки, статусы, согласования, уведомления, контроль сроков и ответственных",
  "Интерфейсы вокруг legal-контура: Telegram-боты, сайты, Mini App, личные кабинеты, клиентские порталы",
  "Интеграции и данные: CRM, ERP, 1C, ЭДО, таблицы, базы данных, отчеты и внутренние панели",
  "AI-интеграции: анализ документов, классификация обращений, генерация черновиков, поиск и суммаризация",
  "Другие автоматизации: если для отдельной цели нужен бот, сайт, Mini App, сервис или программа, можем спроектировать и запустить это тоже",
];

const launchPath = [
  {
    title: "1. Разобрать юридический процесс",
    description: "Понимаем, где именно в legal-контуре теряются документы, заявки, согласования, сроки, ответственность или время команды.",
  },
  {
    title: "2. Собрать карту интеграций",
    description: "Показываем, где нужен AI, где достаточно обычной логики, с какими CRM, ERP, 1C, ЭДО, таблицами или внутренними системами нужно связаться.",
  },
  {
    title: "3. Сделать прототип или пилот",
    description: "Проверяем эффект на реальных документах, заявках, таблицах, чатах или системах клиента.",
  },
  {
    title: "4. Запустить рабочую систему",
    description: "Разворачиваем решение с ролями, журналом действий, интеграциями, уведомлениями, поддержкой и развитием.",
  },
];

const proofPoints = [
  "Начинаем с процесса и результата, а не с модного AI-инструмента.",
  "Юридическая автоматизация остается основной специализацией и точкой доверия.",
  "Можем закрыть весь legal-контур: от анализа документа до бота, сайта, базы данных и интеграции.",
  "Если для результата или для других целей нужен бот, сайт, Mini App, внутренняя программа, AI-модуль или другая автоматизация, можем спроектировать и запустить это тоже.",
  "AI используется там, где он реально помогает: анализ, классификация, поиск, черновики, подсказки.",
];

export default function Home() {
  const contractAIHref = contractAIEntryHref("demo");
  const contractAIExternal = contractAIEntryIsExternal();
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} bg-slate-900 text-slate-100`}>
      <section className="relative overflow-hidden border-b border-slate-800">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(245,158,11,0.16),_transparent_52%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,_rgba(59,130,246,0.14),_transparent_45%)]" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-18">
          <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Юридическая автоматизация + интеграции + смежная разработка
          </span>
          <h1 className="mt-6 max-w-4xl text-3xl font-semibold leading-tight text-white sm:text-4xl md:text-5xl">
            Автоматизируем юридические бизнес-процессы и связываем их с системами компании
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
            AI Verdict помогает юридической функции работать быстрее и прозрачнее: договоры, заявки, согласования,
            комплаенс, документы и контроль сроков. Интегрируем решения с CRM, ERP, 1C, ЭДО, Telegram, сайтами и
            внутренними системами. А если для результата или для других целей нужен бот, сайт, Mini App, внутренняя
            программа, AI-модуль или другая автоматизация, можем спроектировать и запустить это тоже.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <a
              href="#lead-form"
              className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 transition-colors hover:bg-amber-400"
            >
              Разобрать юридический процесс
            </a>
            {contractAIExternal ? (
              <a
                href={contractAIHref}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-slate-700 px-6 py-3 text-center font-semibold text-slate-200 transition-colors hover:border-amber-500 hover:text-amber-300"
              >
                Проверить договор
              </a>
            ) : (
              <Link
                href={contractAIHref}
                className="rounded-lg border border-slate-700 px-6 py-3 text-center font-semibold text-slate-200 transition-colors hover:border-amber-500 hover:text-amber-300"
              >
                Проверить договор
              </Link>
            )}
            <Link
              href="/services/custom-ai"
              className="rounded-lg border border-slate-700 px-6 py-3 text-center font-semibold text-slate-200 transition-colors hover:border-amber-500 hover:text-amber-300"
            >
              Обсудить интеграцию или другое решение
            </Link>
          </div>
          <p className="mt-4 text-sm text-slate-400">
            Или напишите нам в{" "}
            <a
              href={leadBotDeepLink("web_home_intro")}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-400 hover:text-sky-300 underline"
            >
              Telegram
            </a>
            {" "}— ассистент примет задачу в свободной форме.
          </p>
        </div>
      </section>

      <PlatformMap highlightId="site" />

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="max-w-3xl">
          <h2 className="text-3xl md:text-4xl font-semibold text-white">Как начинается автоматизация</h2>
          <p className="mt-4 text-slate-300">
            Не начинаем с ответа “вам нужен бот” или “вам нужен AI”. Сначала разбираем юридический процесс, затем
            выбираем технический контур: AI-модуль, интеграции, интерфейсы, внутренний сервис или простую автоматизацию
            без лишней сложности.
          </p>
        </div>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {launchPath.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-800/60 p-6">
              <h3 className="font-semibold text-amber-300">{item.title}</h3>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-semibold text-white">Маршруты под разные роли</h2>
          <p className="mt-4 text-slate-300">
            Юридический процесс почти всегда связан с бизнесом, операциями и IT. Поэтому показываем задачу не
            списком технологий, а через роли, интеграции и ожидаемый результат.
          </p>
        </div>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {roleCards.map((card) => (
            <article key={card.title} className="rounded-2xl border border-slate-800 bg-slate-800/60 p-7">
              <h3 className="text-xl font-semibold text-white">{card.title}</h3>
              <p className="mt-4 text-slate-300 leading-relaxed">{card.description}</p>
              <Link href={card.href} className="mt-6 inline-flex text-amber-300 hover:text-amber-200 font-semibold">
                {card.cta} →
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40" id="product-entry">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="max-w-3xl">
            <h2 className="text-3xl md:text-4xl font-semibold text-white">Флагманский legal-сценарий: Contract_AI_System</h2>
            <p className="mt-4 text-slate-300">
              Проверка договоров — самый понятный вход в платформу. На нем видно наш базовый принцип: AI помогает
              быстро разобрать документ, но контроль, ответственность и финальное решение остаются у человека.
            </p>
          </div>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5">
              <h3 className="font-semibold text-white">Проверить</h3>
              <p className="mt-2 text-sm text-slate-400">Быстрый анализ договора и подсветка рискованных условий.</p>
            </div>
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5">
              <h3 className="font-semibold text-white">Уточнить</h3>
              <p className="mt-2 text-sm text-slate-400">Комментарий по нормам, альтернативные формулировки и план правок.</p>
            </div>
            <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5">
              <h3 className="font-semibold text-white">Запустить пилот</h3>
              <p className="mt-2 text-sm text-slate-400">Подтвердить эффект на ограниченном процессе и только потом масштабировать в рабочий контур.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h2 className="text-3xl font-semibold text-white">Контур автоматизации</h2>
        <p className="mt-4 max-w-3xl text-slate-300">
          Базовый фокус — юридические бизнес-процессы. Вокруг них собираем рабочий контур, где процесс, AI,
          интерфейсы и интеграции поддерживают друг друга. Отдельные смежные автоматизации тоже можем делать,
          если они нужны для результата или для другой задачи клиента.
        </p>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-5">
          {platformLayers.map((layer) => (
            <article key={layer.title} className="rounded-xl border border-slate-800 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold text-amber-300">{layer.title}</h3>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{layer.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <h2 className="text-3xl font-semibold text-white">Что можно автоматизировать</h2>
          <p className="mt-4 max-w-3xl text-slate-300">
            Юридическая функция — наша сильная специализация и основная точка входа. При этом мы можем проектировать
            и другие автоматизации: если задачу можно описать, связать с данными и превратить в повторяемый маршрут,
            мы можем помочь ее запустить.
          </p>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {cases.map((item) => (
              <div key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 text-slate-200">
                {item}
              </div>
            ))}
          </div>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
            {proofPoints.map((item) => (
              <div key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 text-sm text-slate-300">
                {item}
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href={ROUTES.contentCases}
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-100 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              Контент и кейсы
            </Link>
            <Link
              href={ROUTES.about}
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-100 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              О платформе
            </Link>
          </div>
        </div>
      </section>

      <LeadCaptureForm />
    </main>
  );
}
