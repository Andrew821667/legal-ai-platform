import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES, leadBotDeepLink } from "@/lib/links";
import LeadCaptureForm from "@/components/LeadCaptureForm";
import PlatformMap from "@/components/PlatformMap";
import HeroBackdrop from "@/components/HeroBackdrop";
import PracticeIntersection from "@/components/PracticeIntersection";
import ProductProof from "@/components/ProductProof";
import { isLightOpsTheme } from "@/lib/visualTheme";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "AI Verdict — автоматизация юридических процессов и интеграций",
  description:
    "Автоматизируем договорную работу, юридические заявки, комплаенс и контроль сроков. Оказываем юридическую помощь и разрабатываем прикладные системы.",
  path: "/",
  keywords: ["автоматизация юридических процессов", "автоматизация юридической работы", "Legal AI", "legal ops"],
});

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
    title: "Продуктовая и IT-команда",
    description:
      "Проектируем ботов, сайты, Mini App, внутренние программы, AI-сервисы и интеграции вокруг измеримого бизнес-процесса.",
    href: ROUTES.engineering,
    cta: "Инженерная практика",
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
  "Инженерные проекты: боты, сайты, Mini App, сервисы, программы, AI-модули и интеграции для задач бизнеса",
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
  "Сначала фиксируем проблему и ожидаемый результат. Технологию выбираем после диагностики.",
  "Юристы отвечают за смысл, ограничения и контрольные точки процесса.",
  "Инженеры собирают интерфейсы, интеграции, данные и надежную эксплуатацию.",
  "Отдельные задачи по праву ведет юридическая практика, по разработке — инженерная.",
  "AI берем для анализа, классификации, поиска и черновиков, если это дает измеримую пользу.",
];

export default function Home() {
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} bg-slate-900 text-slate-100`}>
      <section id="assistant-entry" className="relative flex min-h-[680px] items-start overflow-hidden border-b border-slate-800 sm:min-h-[570px] sm:items-center">
        <HeroBackdrop variant="home" tone="light" priority />
        <div className="relative mx-auto w-full max-w-7xl px-4 pb-12 pt-24 sm:px-6 sm:py-28 lg:px-8">
          <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Юридическая практика + инженерная практика
          </span>
          <h1 className="mt-5 max-w-4xl text-[28px] font-semibold leading-[1.2] text-white sm:text-4xl md:text-5xl">
            Автоматизируем юридические бизнес-процессы и связываем их с системами компании
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
            Разбираем действующий процесс, находим ручные потери и собираем рабочее решение: от правил и маршрутов
            согласования до AI, интерфейсов и интеграций. Отдельные юридические и программные задачи тоже берем в работу.
          </p>
          <div className="mt-7 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
            <a
              href="#lead-form"
              className="w-full rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 transition-colors hover:bg-amber-400 sm:w-auto"
            >
              Разобрать юридический процесс
            </a>
            <div className="grid w-full grid-cols-2 gap-2 text-[13px] font-semibold sm:flex sm:w-auto sm:flex-wrap sm:gap-x-5 sm:text-sm">
              <Link href={ROUTES.legalHelp} className="text-slate-700 underline decoration-amber-500/60 underline-offset-4 hover:text-amber-700">
                <span className="sm:hidden">Юридическая →</span><span className="hidden sm:inline">Юридическая практика →</span>
              </Link>
              <Link href={ROUTES.engineering} className="text-slate-700 underline decoration-slate-500/60 underline-offset-4 hover:text-amber-700">
                <span className="sm:hidden">Инженерная →</span><span className="hidden sm:inline">Инженерная практика →</span>
              </Link>
            </div>
          </div>
          <p className="mt-4 hidden text-sm text-slate-600 sm:block">
            Или напишите нам в{" "}
            <a
              href={leadBotDeepLink("web_home_intro")}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-400 hover:text-sky-300 underline"
            >
              Telegram
            </a>
            . Ассистент примет задачу в свободной форме.
          </p>
        </div>
      </section>

      <PracticeIntersection />

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="max-w-3xl">
          <h2 className="text-3xl md:text-4xl font-semibold text-white">Как начинается автоматизация</h2>
          <p className="mt-4 text-slate-300">
            Сначала разбираем юридический процесс: кто что делает, где возникают задержки и какой результат можно
            измерить. После этого становится понятно, нужен ли AI-модуль, интеграция, новый интерфейс или достаточно
            обычной автоматизации.
          </p>
          <Link href={ROUTES.legalAi} className="mt-5 inline-flex font-semibold text-amber-300 hover:text-amber-200">
            ИИ в юридической сфере: возможности, риски и применение →
          </Link>
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
            У юриста, руководителя и IT-команды разные вопросы к одному процессу. Ниже собраны маршруты для каждой роли.
          </p>
        </div>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
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

      <ProductProof />

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h2 className="text-3xl font-semibold text-white">Контур автоматизации</h2>
        <p className="mt-4 max-w-3xl text-slate-300">
          Юридическая модель процесса должна совпасть с тем, как работает система. Поэтому юрист и инженер ведут
          проект вместе: от первой схемы до запуска и поддержки.
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
          <h2 className="text-3xl font-semibold text-white">Где работают наши практики</h2>
          <p className="mt-4 max-w-3xl text-slate-300">
            Запрос сразу попадает профильной команде. В проектах автоматизации юристы и инженеры работают вместе;
            самостоятельные правовые и программные задачи ведут отдельно.
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

      <PlatformMap highlightId="site" />

      <LeadCaptureForm />
    </main>
  );
}
