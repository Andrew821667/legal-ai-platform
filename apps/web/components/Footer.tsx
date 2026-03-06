import Link from "next/link";

type NavItem = {
  name: string;
  href: string;
  external?: boolean;
};

export default function Footer() {
  const navigation: Record<"company" | "services" | "resources", NavItem[]> = {
    company: [
      { name: "Главная", href: "/" },
      { name: "Для юристов", href: "/for-lawyers" },
      { name: "Для бизнеса", href: "/for-business" },
      { name: "Contract_AI_System", href: "/contract-ai-system" },
      { name: "О платформе", href: "/about" },
      { name: "Контакты", href: "/about#contacts" },
    ],
    services: [
      { name: "Решения и услуги", href: "/solutions" },
      { name: "Автоматизация юрфункции", href: "/solutions#automation" },
      { name: "Внедрение AI в legal ops", href: "/solutions#legal-ops" },
      { name: "Интеграции", href: "/solutions#integrations" },
      { name: "Сценарии для бизнеса", href: "/for-business" },
      { name: "Сценарии для юристов", href: "/for-lawyers" },
    ],
    resources: [
      { name: "Контент / Кейсы", href: "/content-cases" },
      { name: "Практические разборы", href: "/content-cases#practical" },
      { name: "Проверить договор", href: "/contract-ai-system#demo" },
      {
        name: "Обсудить внедрение",
        href: "https://t.me/legal_ai_helper_new_bot",
        external: true,
      },
    ],
  };

  const renderNavItem = (item: NavItem) => {
    if (item.external) {
      return (
        <a
          href={item.href}
          className="text-slate-400 hover:text-amber-500 transition-colors text-sm"
          target="_blank"
          rel="noopener noreferrer"
        >
          {item.name}
        </a>
      );
    }

    return (
      <Link href={item.href} className="text-slate-400 hover:text-amber-500 transition-colors text-sm">
        {item.name}
      </Link>
    );
  };

  return (
    <footer className="bg-slate-900 text-slate-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8 mb-8">
          <div className="lg:col-span-2">
            <h3 className="text-2xl font-bold text-white mb-4">Legal AI PRO</h3>
            <p className="text-slate-400 mb-6 leading-relaxed">
              Платформа автоматизации юридической функции: от входящих заявок и договорной работы до управляемых
              AI-процессов в legal ops.
            </p>
            <div className="space-y-2 mb-6">
              <div className="flex items-center gap-2">
                <span className="text-amber-500">✓</span>
                <span className="text-sm">Фокус на прикладном результате, а не на "витринном" AI</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-500">✓</span>
                <span className="text-sm">Контроль качества: правила, роли, аудит решений</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-amber-500">✓</span>
                <span className="text-sm">Пилоты с понятной метрикой экономии времени и рисков</span>
              </div>
            </div>

            <div className="flex gap-4">
              <a
                href="https://t.me/legal_ai_helper_new_bot"
                className="bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white p-3 rounded-lg transition-all"
                aria-label="Telegram Бот"
                title="Telegram Бот"
                target="_blank"
                rel="noopener noreferrer"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18.717-.962 3.383-1.362 4.486-.168.464-.5 1.395-.882 1.395-.297 0-.54-.18-.748-.333-.208-.153-1.024-.668-1.562-.998-.16-.098-.718-.443-.718-.808 0-.235.248-.428.553-.645.787-.558 1.738-1.234 2.278-1.638.27-.202.135-.32-.15-.12-.672.473-1.946 1.293-2.345 1.554-.18.118-.36.235-.652.235-.382 0-.803-.118-1.215-.235-.472-.135-.922-.27-1.362-.405-.27-.083-.54-.166-.54-.41 0-.258.27-.345.54-.432.472-.152 4.77-1.838 5.562-2.155.09-.036.27-.09.36-.09.18 0 .36.09.36.333 0 .055-.018.11-.027.164z" />
                </svg>
              </a>
              <a
                href="mailto:a.popov.gv@gmail.com"
                className="bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white p-3 rounded-lg transition-all"
                aria-label="Email"
                title="Email"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Компания</h4>
            <ul className="space-y-3">
              {navigation.company.map((item) => (
                <li key={item.name}>{renderNavItem(item)}</li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Решения</h4>
            <ul className="space-y-3">
              {navigation.services.map((item) => (
                <li key={item.name}>{renderNavItem(item)}</li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Ресурсы</h4>
            <ul className="space-y-3">
              {navigation.resources.map((item) => (
                <li key={item.name}>{renderNavItem(item)}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-slate-800 pt-8 pb-8" id="contacts">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="flex items-start gap-3">
              <div className="text-amber-500 text-xl">📞</div>
              <div>
                <div className="text-white font-medium mb-1">Телефон</div>
                <a href="tel:+79092330909" className="text-slate-400 hover:text-amber-500 transition-colors text-sm">
                  +7 909 233-09-09
                </a>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="text-amber-500 text-xl">📧</div>
              <div>
                <div className="text-white font-medium mb-1">Email</div>
                <a
                  href="mailto:a.popov.gv@gmail.com"
                  className="text-slate-400 hover:text-amber-500 transition-colors text-sm"
                >
                  a.popov.gv@gmail.com
                </a>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="text-amber-500 text-xl">🤖</div>
              <div>
                <div className="text-white font-medium mb-1">Telegram бот</div>
                <a
                  href="https://t.me/legal_ai_helper_new_bot"
                  className="text-slate-400 hover:text-amber-500 transition-colors text-sm"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Ассистент Legal AI Pro
                </a>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="text-amber-500 text-xl">📢</div>
              <div>
                <div className="text-white font-medium mb-1">Telegram канал</div>
                <a
                  href="https://t.me/legal_ai_pro"
                  className="text-slate-400 hover:text-amber-500 transition-colors text-sm"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  @legal_ai_pro
                </a>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 pt-8 pb-6">
          <div className="text-center text-sm text-slate-500 leading-relaxed max-w-5xl mx-auto space-y-3">
            <p>
              <strong className="text-slate-400">Legal AI PRO</strong>: внедрение AI в юридическую функцию,
              автоматизация договорных и типовых правовых процессов, проектирование legal ops контуров.
            </p>
            <div className="pt-2 flex items-center justify-center gap-4 text-xs">
              <span className="text-emerald-400">
                ✓ Обновлено:{" "}
                {new Date().toLocaleDateString("ru-RU", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </span>
              <span className="text-slate-600">|</span>
              <Link href="/about" className="text-amber-500 hover:text-amber-400 transition-colors">
                О платформе и методологии
              </Link>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 pt-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-slate-500 text-sm">© {new Date().getFullYear()} Legal AI PRO. Все права защищены.</p>
          <div className="flex gap-6 text-sm">
            <Link href="/privacy" className="text-slate-500 hover:text-amber-500 transition-colors">
              Политика конфиденциальности
            </Link>
            <Link href="/terms" className="text-slate-500 hover:text-amber-500 transition-colors">
              Условия использования
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
