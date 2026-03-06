import Link from "next/link";
import { ROUTES, leadBotDeepLink, readerBotDeepLink } from "@/lib/links";

type CtaFrameworkPanelProps = {
  leadStart: string;
  miniAppHref?: string;
  title?: string;
  className?: string;
};

export default function CtaFrameworkPanel({
  leadStart,
  miniAppHref = ROUTES.miniApp,
  title = "Единый маршрут: Узнать -> Проверить -> Внедрить",
  className = "",
}: CtaFrameworkPanelProps) {
  return (
    <div className={`rounded-2xl border border-amber-500/35 bg-slate-950/70 p-5 ${className}`.trim()}>
      <p className="text-xs uppercase tracking-wide text-amber-300/90">{title}</p>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <a
          href={readerBotDeepLink("discover")}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-slate-700 px-4 py-3 text-center font-semibold text-slate-100 hover:border-amber-400 hover:text-amber-200 transition-colors"
        >
          🧠 Узнать
        </a>
        <a
          href={readerBotDeepLink("validate")}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg bg-amber-500 px-4 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
        >
          🧪 Проверить
        </a>
        <a
          href={leadBotDeepLink(leadStart)}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-sky-500/60 px-4 py-3 text-center font-semibold text-sky-200 hover:border-sky-300 transition-colors"
        >
          🛠 Внедрить
        </a>
      </div>
      <div className="mt-4 flex flex-wrap gap-3 text-sm">
        <Link
          href={miniAppHref}
          className="rounded-lg border border-slate-700 px-3 py-2 text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
        >
          🧩 Продолжить в mini-app
        </Link>
        <a
          href={readerBotDeepLink("solutions")}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-slate-700 px-3 py-2 text-slate-200 hover:border-sky-400 hover:text-sky-300 transition-colors"
        >
          🧰 Reader: Решения
        </a>
      </div>
    </div>
  );
}
