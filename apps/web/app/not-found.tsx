import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Страница не найдена",
  description: "Запрошенная страница не найдена на сайте AI Verdict.",
  robots: {
    index: false,
    follow: true,
    nocache: true,
  },
};

export default function NotFound() {
  return (
    <main className="min-h-[70vh] bg-slate-950 px-4 py-24 text-slate-100">
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-400">Ошибка 404</p>
        <h1 className="mt-4 text-4xl font-semibold text-white">Страница не найдена</h1>
        <p className="mt-5 text-slate-300">
          Возможно, адрес изменился или в ссылке есть ошибка. Вернитесь на главную или откройте каталог решений.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link href="/" className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400">
            На главную
          </Link>
          <Link href="/solutions" className="rounded-lg border border-slate-700 px-5 py-3 font-semibold hover:border-amber-500">
            Посмотреть решения
          </Link>
        </div>
      </div>
    </main>
  );
}
