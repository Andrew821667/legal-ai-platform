import Link from "next/link";
import { ROUTES } from "@/lib/links";

const tools = [
  {
    title: "Contract_AI_System",
    description: "Анализ договора, подсветка рисков, рекомендации по правкам и подготовке согласования.",
    href: ROUTES.contractAI,
  },
  {
    title: "История анализов",
    description: "Продолжение предыдущих проверок и контроль результата пилота.",
    href: ROUTES.miniAppProfile,
  },
  {
    title: "Будущие инструменты",
    description: "Сценарии для претензионной, комплаенса и внутренних legal ops процессов.",
    href: ROUTES.solutions,
  },
];

export default function MiniAppToolsPage() {
  return (
    <section className="space-y-4">
      {tools.map((tool) => (
        <article key={tool.title} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h2 className="text-base font-semibold text-white">{tool.title}</h2>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">{tool.description}</p>
          <Link
            href={tool.href}
            className="mt-4 inline-flex rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть
          </Link>
        </article>
      ))}
    </section>
  );
}
