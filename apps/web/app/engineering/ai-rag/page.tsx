import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["ai-rag"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: ROUTES.aiRag,
  socialImage: "/engineering/opengraph-image",
  keywords: [
    "разработка RAG системы",
    "RAG для бизнеса",
    "AI по документам компании",
    "поиск по базе знаний с ИИ",
    "корпоративный AI ассистент",
    "внедрение RAG",
    "разработка AI сервиса",
  ],
});

export default function AiRagPage() {
  return <ServiceDetailPage service={service} path={ROUTES.aiRag} />;
}
