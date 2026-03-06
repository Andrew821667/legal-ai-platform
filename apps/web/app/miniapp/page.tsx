import Link from "next/link";
import { ROUTES } from "@/lib/links";

const highlights = [
  "Новые AI-обновления с практическим юридическим эффектом",
  "2 сценария для ускорения договорного потока",
  "1 готовый шаблон для пилота legal ops",
];

const quickActions = [
  { label: "Открыть контент", href: ROUTES.miniAppContent },
  { label: "Проверить договор", href: `${ROUTES.contractAI}#demo` },
  { label: "Сценарии внедрения", href: ROUTES.miniAppSolutions },
];

export default function MiniAppHomePage() {
  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Важное сегодня</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-300">
          {highlights.map((item) => (
            <li key={item}>• {item}</li>
          ))}
        </ul>
      </article>

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Для вас</h2>
        <p className="mt-2 text-sm text-slate-300">
          На основе интересов предлагаем начать с Contract_AI_System и затем перейти к roadmap внедрения.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-2">
          {quickActions.map((action) => (
            <Link
              key={action.label}
              href={action.href}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              {action.label}
            </Link>
          ))}
        </div>
      </article>

      <article className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
        <h2 className="text-base font-semibold text-white">Продолжить работу</h2>
        <p className="mt-2 text-sm text-slate-200">
          Последние действия: анализ договора, подбор практических кейсов, формирование шага внедрения.
        </p>
      </article>
    </section>
  );
}
