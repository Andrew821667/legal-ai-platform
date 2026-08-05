import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES, contractAIEntryHref, contractAIEntryIsExternal, leadBotDeepLink } from "@/lib/links";
import LeadCaptureForm from "@/components/LeadCaptureForm";
import PlatformMap from "@/components/PlatformMap";
import HeroBackdrop from "@/components/HeroBackdrop";
import { isLightOpsTheme } from "@/lib/visualTheme";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "AI Verdict — автоматизация юридических процессов и интеграций",
  description:
    "Юридическая и инженерная практики AI Verdict автоматизируют юридическую функцию, а также ведут профильные юридические и инженерные проекты.",
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

const foundationPractices = [
  {
    label: "Базовая практика",
    title: "Юридическая практика",
    description:
      "Юристы решают договорные, судебные, корпоративные и личные правовые задачи, а в совместных проектах отвечают за логику автоматизируемого процесса.",
    href: ROUTES.legalHelp,
    cta: "Обратиться к юристу",
  },
  {
    label: "Базовая практика",
    title: "Инженерная практика",
    description:
      "Инженеры создают ботов, сайты, Mini App, внутренние программы, AI-модули и интеграции, а в совместных проектах строят технологический контур legal automation.",
    href: ROUTES.engineering,
    cta: "Обсудить инженерный проект",
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
  "Начинаем с процесса и результата, а не с модного AI-инструмента.",
  "Юридическая автоматизация — ключевое пересечение юридической и инженерной практик.",
  "Можем закрыть весь legal-контур: от анализа документа до бота, сайта, базы данных и интеграции.",
  "Самостоятельные программные задачи ведет инженерная практика с собственной диагностикой, архитектурой и метриками.",
  "AI используется там, где он реально помогает: анализ, классификация, поиск, черновики, подсказки.",
];

export default function Home() {
  const contractAIHref = contractAIEntryHref("demo");
  const contractAIExternal = contractAIEntryIsExternal();
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} bg-slate-900 text-slate-100`}>
      <section className="relative overflow-hidden border-b border-slate-800">
        <HeroBackdrop variant="home" tone="light" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-18">
          <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Юридическая практика + инженерная практика
          </span>
          <h1 className="mt-6 max-w-4xl text-3xl font-semibold leading-tight text-white sm:text-4xl md:text-5xl">
            Автоматизируем юридические бизнес-процессы и связываем их с системами компании
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
            AI Verdict объединяет юридическую и инженерную практики. На их стыке мы автоматизируем юридическую
            функцию: договоры, заявки, согласования, комплаенс, документы и контроль сроков. Каждая практика также
            ведет профильные проекты самостоятельно — юридическую помощь или разработку прикладных систем.
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
              href={ROUTES.engineering}
              className="rounded-lg border border-slate-700 px-6 py-3 text-center font-semibold text-slate-200 transition-colors hover:border-amber-500 hover:text-amber-300"
            >
              Обсудить разработку и AI
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

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-amber-300">Архитектура AI Verdict</p>
            <h2 className="mt-2 text-2xl font-semibold text-white md:text-3xl">Две практики. Одна ключевая специализация</h2>
            <p className="mt-3 text-slate-300">
              Юридическая и инженерная экспертиза существуют как самостоятельные направления. Для автоматизации
              юридической функции они работают вместе: право определяет логику процесса, инженерия превращает ее в
              устойчивую систему.
            </p>
          </div>
          <article className="mt-8 rounded-lg border border-amber-500/40 bg-slate-900/80 p-6 md:p-8">
            <p className="text-xs font-semibold uppercase text-amber-300">Ключевое пересечение</p>
            <div className="mt-3 grid gap-5 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <h3 className="text-2xl font-semibold text-white">Автоматизация юридической функции</h3>
                <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-300">
                  Диагностика legal-процесса, юридическая модель, интерфейсы, AI, интеграции и эксплуатация в одном
                  проекте с общей ответственностью за результат.
                </p>
              </div>
              <Link href={ROUTES.solutions} className="font-semibold text-amber-300 hover:text-amber-200">
                Посмотреть решения →
              </Link>
            </div>
          </article>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            {foundationPractices.map((practice) => (
              <article key={practice.title} className="rounded-lg border border-slate-700 bg-slate-900/60 p-6">
                <p className="text-xs font-semibold uppercase text-amber-300">{practice.label}</p>
                <h3 className="mt-2 text-xl font-semibold text-white">{practice.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-300">{practice.description}</p>
                <Link href={practice.href} className="mt-5 inline-flex font-semibold text-amber-300 hover:text-amber-200">
                  {practice.cta} →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

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

      <section className="border-y border-slate-800 bg-slate-800/40" id="product-entry">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="max-w-3xl">
            <h2 className="text-3xl md:text-4xl font-semibold text-white">Флагманский legal-сценарий: Contract AI</h2>
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
          <Link
            href={ROUTES.contractAI}
            className="mt-7 inline-flex font-semibold text-sky-300 transition-colors hover:text-sky-200"
          >
            Подробнее о Contract AI и бесплатной проверке договоров →
          </Link>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h2 className="text-3xl font-semibold text-white">Контур автоматизации</h2>
        <p className="mt-4 max-w-3xl text-slate-300">
          В legal automation две практики работают как одна проектная команда: юридическая определяет смысл,
          ограничения и контрольные точки процесса, инженерная отвечает за интерфейсы, AI, интеграции и надежную
          эксплуатацию. В самостоятельных задачах каждая практика сохраняет свой профиль и ответственность.
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
            Запрос получает команда с нужной экспертизой. Юридическая автоматизация объединяет обе практики,
            юридическая помощь остается в правовом контуре, а разработка для других целей — в инженерном.
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
