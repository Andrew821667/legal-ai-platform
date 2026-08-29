import { MetadataRoute } from "next";

import { AI_LAW_REVIEWED_AT, aiLawComments } from "@/lib/aiLawComments";
import { guides } from "@/lib/guidesData";
import { LEGAL_AI_REVIEWED_AT, legalAiTopics } from "@/lib/legalAiTopics";
import { LEGAL_HELP_REVIEWED_AT, legalHelpPageList } from "@/lib/legalHelpPages";
import { legalHelpRegionList } from "@/lib/legalHelpRegions";
import { SEO_SITE_URL } from "@/lib/seo";

type SitemapPage = {
  path: string;
  lastModified: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
};

const marketingUpdatedAt = "2026-07-15";
const practiceUpdatedAt = "2026-08-05";
const legalAiUpdatedAt = "2026-08-13";
const visibilityUpdatedAt = "2026-08-13";

const pages: SitemapPage[] = [
  { path: "", lastModified: visibilityUpdatedAt, changeFrequency: "weekly", priority: 1 },
  { path: "/legal-ai", lastModified: legalAiUpdatedAt, changeFrequency: "monthly", priority: 0.95 },
  { path: "/for-lawyers", lastModified: LEGAL_AI_REVIEWED_AT, changeFrequency: "monthly", priority: 0.9 },
  { path: "/for-business", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.9 },
  { path: "/solutions", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.85 },
  { path: "/services", lastModified: practiceUpdatedAt, changeFrequency: "monthly", priority: 0.85 },
  { path: "/legal-help", lastModified: practiceUpdatedAt, changeFrequency: "weekly", priority: 0.9 },
  { path: "/legal-help/business", lastModified: LEGAL_HELP_REVIEWED_AT, changeFrequency: "monthly", priority: 0.85 },
  { path: "/legal-help/individuals", lastModified: LEGAL_HELP_REVIEWED_AT, changeFrequency: "monthly", priority: 0.85 },
  { path: "/legal-help/regions", lastModified: LEGAL_HELP_REVIEWED_AT, changeFrequency: "monthly", priority: 0.8 },
  { path: "/services/contracts-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.85 },
  { path: "/contract-ai-system", lastModified: visibilityUpdatedAt, changeFrequency: "weekly", priority: 0.9 },
  { path: "/services/litigation-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.75 },
  { path: "/services/compliance-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.75 },
  { path: "/services/corporate-ma-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.7 },
  { path: "/services/tax-compliance-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.7 },
  { path: "/services/land-law-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.7 },
  { path: "/services/legal-analytics-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.7 },
  { path: "/engineering", lastModified: practiceUpdatedAt, changeFrequency: "monthly", priority: 0.85 },
  { path: "/services/outsourcing-ai", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.65 },
  { path: "/cases", lastModified: visibilityUpdatedAt, changeFrequency: "monthly", priority: 0.8 },
  { path: "/content-cases", lastModified: "2026-07-28", changeFrequency: "weekly", priority: 0.8 },
  { path: "/ai-law", lastModified: AI_LAW_REVIEWED_AT, changeFrequency: "weekly", priority: 0.9 },
  { path: "/guides", lastModified: LEGAL_AI_REVIEWED_AT, changeFrequency: "weekly", priority: 0.85 },
  { path: "/about", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.7 },
  { path: "/team", lastModified: visibilityUpdatedAt, changeFrequency: "monthly", priority: 0.75 },
  { path: "/regions", lastModified: marketingUpdatedAt, changeFrequency: "monthly", priority: 0.55 },
  { path: "/privacy", lastModified: "2026-07-14", changeFrequency: "yearly", priority: 0.3 },
  { path: "/terms", lastModified: "2026-07-13", changeFrequency: "yearly", priority: 0.3 },
  { path: "/user-agreement", lastModified: "2026-07-13", changeFrequency: "yearly", priority: 0.25 },
  { path: "/ai-policy", lastModified: "2026-07-13", changeFrequency: "yearly", priority: 0.4 },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = SEO_SITE_URL;
  const guidePages: SitemapPage[] = guides.map((guide) => ({
    path: `/guides/${guide.slug}`,
    lastModified: guide.updatedAt,
    changeFrequency: "monthly",
    priority: 0.8,
  }));
  const aiLawPages: SitemapPage[] = aiLawComments.map((comment) => ({
    path: `/ai-law/${comment.slug}`,
    lastModified: comment.reviewedAt,
    changeFrequency: "monthly",
    priority: 0.85,
  }));
  const legalPages: SitemapPage[] = legalHelpPageList.map((page) => ({
    path: `/legal-help/${page.slug}`,
    lastModified: LEGAL_HELP_REVIEWED_AT,
    changeFrequency: "monthly",
    priority: 0.75,
  }));
  const legalRegionPages: SitemapPage[] = legalHelpRegionList.map((region) => ({
    path: `/legal-help/regions/${region.slug}`,
    lastModified: LEGAL_HELP_REVIEWED_AT,
    changeFrequency: "monthly",
    priority: 0.7,
  }));
  const legalAiPages: SitemapPage[] = legalAiTopics.map((topic) => ({
    path: `/legal-ai/${topic.slug}`,
    lastModified: topic.reviewedAt ?? LEGAL_AI_REVIEWED_AT,
    changeFrequency: "monthly",
    priority: 0.8,
  }));

  return [...pages, ...aiLawPages, ...legalAiPages, ...legalPages, ...legalRegionPages, ...guidePages].map((page) => ({
    url: `${baseUrl}${page.path}`,
    lastModified: new Date(`${page.lastModified}T00:00:00.000Z`),
    changeFrequency: page.changeFrequency,
    priority: page.priority,
  }));
}
