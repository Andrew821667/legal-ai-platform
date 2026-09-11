import type { Metadata } from "next";
import Script from "next/script";

export const metadata: Metadata = {
  title: "Рабочее место юриста | AI Verdict",
  description: "Клиенты, обращения, документы и договоры практики.",
  // Раздел не для поисковиков: он показывает данные клиентов.
  robots: { index: false, follow: false, nocache: true },
  // «Добавить на экран Домой» в Safari — самостоятельный запуск без
  // Telegram. apple-mobile-web-app-capable убирает адресную строку и chrome
  // браузера, оставляя раздел похожим на обычное приложение; иконка
  // берётся из app/lawyer/apple-icon.tsx (next/og, без внешних инструментов
  // конвертации SVG → PNG на боевом хосте).
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Рабочее место",
  },
};

export const viewport = {
  themeColor: "#f7f8fb",
  colorScheme: "light",
};

export default function LawyerLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      <main className="lw-page min-h-screen text-lw-base">
        {/* На телефоне — одна колонка; на ноутбуке — список слева, карточка
            справа. Раньше был тот же мобильный столбец, отцентрированный посреди
            широкого экрана, с пустотой по бокам. */}
        <div className="mx-auto w-full max-w-2xl px-4 pb-16 pt-5 lg:max-w-6xl">{children}</div>
      </main>
    </>
  );
}
