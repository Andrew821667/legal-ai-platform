import type { Metadata } from "next";
import Link from "next/link";
import { regions } from "@/lib/regionsData";

export const metadata: Metadata = {
  title: "Регионы",
  description:
    "Региональные страницы Legal AI PRO: Москва, Санкт-Петербург и ключевые аграрные регионы России.",
  alternates: {
    canonical: "/regions",
  },
  openGraph: {
    title: "Регионы | Legal AI PRO",
    description:
      "Выберите регион и посмотрите, как AI может усилить юридическую функцию вашей компании.",
    url: "/regions",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Регионы | Legal AI PRO",
    description:
      "Выберите регион и посмотрите, как AI может усилить юридическую функцию вашей компании.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RegionsPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Регионы присутствия
        </h1>
        <p className="text-lg text-slate-600 mb-10 max-w-3xl">
          Работаем по всей России. Ниже собрали региональные страницы для
          Москвы, Санкт-Петербурга и сильных агропромышленных регионов.
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
                Открыть страницу региона →
              </span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
