import { faqData } from "@/lib/faqData";
import { serviceDetails } from "@/lib/serviceDetailData";
import { caseStudies } from "@/lib/caseStudiesData";
import { guides } from "@/lib/guidesData";

export type KnowledgeItem = {
  id: string;
  type: "faq" | "service" | "case" | "guide";
  title: string;
  text: string;
  href: string;
};

const SITE_URL_FALLBACK = "https://ai-verdict.ru";

function siteUrl(): string {
  return (process.env.NEXT_PUBLIC_SITE_URL || SITE_URL_FALLBACK).replace(/\/+$/, "");
}

function absoluteHref(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${siteUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * Снимок знаний компании для RAG-контекста ассистента (лид-бот, apps/lead-bot/legacy).
 *
 * Не отдельная база — тот же контент, что уже публикуется на сайте: услуги,
 * FAQ, типовые сценарии внедрения, методологические статьи. Один источник
 * правды — эти же lib/*Data.ts используются страницами сайта; здесь только
 * сборка в плоский список для поиска.
 */
export function buildKnowledgeSnapshot(): KnowledgeItem[] {
  const items: KnowledgeItem[] = [];

  for (const [index, item] of faqData.entries()) {
    items.push({
      id: `faq-${index}`,
      type: "faq",
      title: item.question,
      text: item.answer,
      href: absoluteHref("/#faq"),
    });
  }

  for (const service of Object.values(serviceDetails)) {
    items.push({
      id: `service-${service.slug}`,
      type: "service",
      title: service.title,
      text: [service.description, service.intro, service.shortAnswer].filter(Boolean).join(" "),
      href: absoluteHref(`/services/${service.slug}`),
    });
    for (const [faqIndex, faq] of service.faq.entries()) {
      items.push({
        id: `service-${service.slug}-faq-${faqIndex}`,
        type: "faq",
        title: faq.question,
        text: faq.answer,
        href: absoluteHref(`/services/${service.slug}`),
      });
    }
  }

  // Типовые сценарии внедрения — проектные модели, не именованные кейсы
  // клиентов с подтверждённым эффектом (см. caseStudiesData.ts). Текст
  // снимка не должен звучать как готовый результат — только как сценарий.
  for (const [index, item] of caseStudies.entries()) {
    items.push({
      id: `case-${index}`,
      type: "case",
      title: `Типовой сценарий: ${item.title}`,
      text: [
        `Проблема: ${item.problem.join(" ")}`,
        `Что меняем: ${item.solution.join(" ")}`,
        `Ожидаемый эффект (после измерения на пилоте): ${item.result.join(" ")}`,
      ].join(" "),
      href: absoluteHref(item.href),
    });
  }

  for (const guide of guides) {
    items.push({
      id: `guide-${guide.slug}`,
      type: "guide",
      title: guide.title,
      text: [guide.excerpt, guide.checklist.length ? `Чек-лист: ${guide.checklist.join("; ")}` : ""]
        .filter(Boolean)
        .join(" "),
      href: absoluteHref(`/guides/${guide.slug}`),
    });
  }

  return items;
}
