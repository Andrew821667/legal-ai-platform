import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Личный кабинет | AI Verdict",
  description: "Ваши обращения, договоры, акты и NDA.",
  // Раздел не для поисковиков: он показывает персональные данные клиента.
  robots: { index: false, follow: false, nocache: true },
};

export const viewport: Viewport = {
  colorScheme: "light",
};

/**
 * Header/Footer/WebAssistant сайта приходят из AppShell (/cabinet — обычный,
 * не chromeless маршрут, в отличие от /miniapp и /lawyer). Светлая тема —
 * тем же механизмом, что у Mini App: .miniapp-light-ops в globals.css
 * перекрашивает тёмные slate/red/emerald-классы ClientCases.tsx без единой
 * правки самих классов. Telegram-скрипт (telegram-web-app.js) здесь не
 * нужен — кабинет на сайте не открывается внутри Telegram Mini App.
 */
export default function CabinetLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="miniapp-light-ops min-h-screen pb-16 pt-24">
      <div className="mx-auto w-full max-w-3xl px-4">{children}</div>
    </div>
  );
}
