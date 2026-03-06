import { MetadataRoute } from "next";
import { regions } from "@/lib/regionsData";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://legalaipro.ru";
  const lastModified = new Date(process.env.NEXT_PUBLIC_SITE_UPDATED_AT || "2026-03-06");

  const staticPages: Array<{ path: string; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"]; priority: number }> = [
    { path: "", changeFrequency: "weekly", priority: 1 },
    { path: "/for-lawyers", changeFrequency: "weekly", priority: 0.9 },
    { path: "/for-business", changeFrequency: "weekly", priority: 0.9 },
    { path: "/contract-ai-system", changeFrequency: "weekly", priority: 0.95 },
    { path: "/solutions", changeFrequency: "weekly", priority: 0.85 },
    { path: "/content-cases", changeFrequency: "weekly", priority: 0.85 },
    { path: "/about", changeFrequency: "monthly", priority: 0.75 },
    { path: "/privacy", changeFrequency: "monthly", priority: 0.5 },
    { path: "/terms", changeFrequency: "monthly", priority: 0.5 },
    { path: "/services", changeFrequency: "monthly", priority: 0.7 },
    { path: "/cases", changeFrequency: "monthly", priority: 0.7 },
    { path: "/team", changeFrequency: "monthly", priority: 0.6 },
    { path: "/regions", changeFrequency: "monthly", priority: 0.7 },
    { path: "/services/contracts-ai", changeFrequency: "monthly", priority: 0.75 },
    { path: "/services/litigation-ai", changeFrequency: "monthly", priority: 0.75 },
    { path: "/services/compliance-ai", changeFrequency: "monthly", priority: 0.75 },
    { path: "/services/corporate-ma-ai", changeFrequency: "monthly", priority: 0.75 },
    { path: "/services/tax-compliance-ai", changeFrequency: "monthly", priority: 0.75 },
    { path: "/services/land-law-ai", changeFrequency: "monthly", priority: 0.7 },
    { path: "/services/legal-analytics-ai", changeFrequency: "monthly", priority: 0.7 },
    { path: "/services/custom-ai", changeFrequency: "monthly", priority: 0.7 },
    { path: "/services/outsourcing-ai", changeFrequency: "monthly", priority: 0.7 },
  ];

  const staticUrls: MetadataRoute.Sitemap = staticPages.map((page) => ({
    url: `${baseUrl}${page.path}`,
    lastModified,
    changeFrequency: page.changeFrequency,
    priority: page.priority,
  }));

  const regionUrls: MetadataRoute.Sitemap = regions.map((region) => ({
    url: `${baseUrl}/regions/${region.slug}`,
    lastModified,
    changeFrequency: "monthly",
    priority: 0.65,
  }));

  return [...staticUrls, ...regionUrls];
}
