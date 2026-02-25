import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRegionBySlug, regions } from "@/lib/regionsData";

interface RegionPageProps {
  params: Promise<{ slug: string }>;
}

export function generateStaticParams() {
  return regions.map((region) => ({ slug: region.slug }));
}

export async function generateMetadata({
  params,
}: RegionPageProps): Promise<Metadata> {
  const { slug } = await params;
  const region = getRegionBySlug(slug);

  if (!region) {
    return {
      title: "Регион не найден",
      robots: { index: false, follow: false },
    };
  }

  return {
    title: `Legal AI в ${region.name}`,
    description: `Автоматизация юридической работы в регионе ${region.name}: договоры, судебная работа, комплаенс и аналитика.`,
    alternates: {
      canonical: `/regions/${region.slug}`,
    },
    openGraph: {
      title: `Legal AI в ${region.name} | Legal AI PRO`,
      description: `AI-решения для юридических команд в регионе ${region.name}.`,
      url: `/regions/${region.slug}`,
      type: "article",
    },
    twitter: {
      card: "summary",
      title: `Legal AI в ${region.name} | Legal AI PRO`,
      description: `AI-решения для юридических команд в регионе ${region.name}.`,
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default async function RegionPage({ params }: RegionPageProps) {
  const { slug } = await params;
  const region = getRegionBySlug(slug);

  if (!region) {
    notFound();
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/regions" className="hover:text-amber-600">
            Регионы
          </Link>{" "}
          / {region.name}
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          AI для юридической функции в регионе {region.name}
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          {region.shortDescription} Внедряем понятные решения для сокращения
          рутины и ускорения юридических процессов.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что особенно актуально в регионе
          </h2>
          <ul className="space-y-3 text-slate-700">
            {region.focus.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Рекомендуемые решения
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              href="/services/contracts-ai"
              className="rounded-lg border border-slate-200 p-4 hover:bg-slate-50"
            >
              Автоматизация договорной работы →
            </Link>
            <Link
              href="/services/litigation-ai"
              className="rounded-lg border border-slate-200 p-4 hover:bg-slate-50"
            >
              Автоматизация судебной работы →
            </Link>
            <Link
              href="/services/compliance-ai"
              className="rounded-lg border border-slate-200 p-4 hover:bg-slate-50"
            >
              Автоматизация комплаенса →
            </Link>
            <Link
              href="/services/corporate-ma-ai"
              className="rounded-lg border border-slate-200 p-4 hover:bg-slate-50"
            >
              Корпоративное право и M&A →
            </Link>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить проект по региону
          </a>
          <Link
            href="/cases"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Посмотреть кейсы
          </Link>
        </div>
      </section>
    </main>
  );
}
