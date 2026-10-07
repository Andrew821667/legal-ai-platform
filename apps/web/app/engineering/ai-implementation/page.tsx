import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["ai-implementation"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: ROUTES.aiImplementation,
  socialImage: "/engineering/opengraph-image",
  keywords: [
    "внедрение ИИ в бизнес",
    "как внедрить ИИ в компанию",
    "внедрение искусственного интеллекта",
    "ИИ для бизнес процессов",
    "автоматизация бизнеса с ИИ",
    "пилот ИИ для компании",
    "аудит внедрения ИИ",
  ],
});

export default function AiImplementationPage() {
  return <ServiceDetailPage service={service} path={ROUTES.aiImplementation} />;
}
