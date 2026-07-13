import type { Metadata } from "next";
import Link from "next/link";
import { regions } from "@/lib/regionsData";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "Legal AI для команд в регионах России",
  description:
    "Удаленная диагностика и внедрение Legal AI для юридических команд в России: договоры, судебная работа, комплаенс и аналитика.",
  path: "/regions",
});

export default function RegionsPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Работа с юридическими командами в регионах России
        </h1>
        <p className="text-lg text-slate-600 mb-10 max-w-3xl">
          Проекты можно диагностировать и запускать удаленно. Ниже собраны ориентиры
          по типовым задачам разных регионов; список не означает наличие локальных офисов.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {regions.map((region) => (
            <Link
              key={region.slug}
              href={`/regions/${region.slug}`}
              className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-shadow"
            >
              <h2 className="text-xl font-semibold text-slate-900 mb-3">
                {region.name}
              </h2>
              <p className="text-slate-600 mb-4">{region.shortDescription}</p>
              <span className="text-amber-600 font-semibold">
                Посмотреть сценарии региона →
              </span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
