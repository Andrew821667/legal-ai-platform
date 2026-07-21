import type { Metadata } from "next";
import { notFound } from "next/navigation";

import LegalHelpServicePage from "@/components/LegalHelpServicePage";
import { getLegalHelpPage, legalHelpPageList } from "@/lib/legalHelpPages";
import { createPageMetadata } from "@/lib/seo";

type LegalHelpDetailPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  return legalHelpPageList.map((page) => ({ slug: page.slug }));
}

export async function generateMetadata({ params }: LegalHelpDetailPageProps): Promise<Metadata> {
  const { slug } = await params;
  const page = getLegalHelpPage(slug);
  if (!page) {
    return { title: "Юридическая услуга не найдена", robots: { index: false, follow: false } };
  }

  return createPageMetadata({
    title: page.seoTitle,
    description: page.description,
    path: `/legal-help/${page.slug}`,
    keywords: page.keywords,
  });
}

export default async function LegalHelpDetailPage({ params }: LegalHelpDetailPageProps) {
  const { slug } = await params;
  const page = getLegalHelpPage(slug);
  if (!page) notFound();

  return <LegalHelpServicePage page={page} />;
}
