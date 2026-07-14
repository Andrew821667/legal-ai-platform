import type { Metadata } from "next";
import Link from "next/link";
import { regions } from "@/lib/regionsData";
import { createPageMetadata } from "@/lib/seo";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "Legal AI для команд в регионах России",
  description:
    "Удаленная диагностика и внедрение Legal AI для юридических команд в России: договоры, судебная работа, комплаенс и аналитика.",
  path: "/regions",
});

export default function RegionsPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="relative overflow-hidden border-b border-slate-300 bg-slate-100">
        <HeroBackdrop variant="collaboration" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-32 sm:px-6 lg:px-8">
          <h1 className="max-w-4xl text-4xl font-bold text-slate-900 md:text-5xl">
            Работа с юридическими командами в регионах России
          </h1>
          <p className="mt-6 max-w-3xl text-lg text-slate-700">
            Проекты можно диагностировать и запускать удаленно. Ниже собраны ориентиры
            по типовым задачам разных регионов; список не означает наличие локальных офисов.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
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
