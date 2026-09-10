import type { Metadata } from "next";
import Script from "next/script";

export const metadata: Metadata = {
  title: "Рабочее место юриста | AI Verdict",
  description: "Клиенты, обращения, документы и договоры практики.",
  // Раздел не для поисковиков: он показывает данные клиентов.
  robots: { index: false, follow: false, nocache: true },
};

export default function LawyerLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto w-full max-w-2xl px-4 pb-16 pt-5">{children}</div>
      </main>
    </>
  );
}
