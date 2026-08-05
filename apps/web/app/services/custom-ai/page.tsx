import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["custom-ai"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: `/services/${service.slug}`,
  keywords: [
    "разработка программного обеспечения",
    "разработка Telegram ботов",
    "разработка Mini App",
    "разработка AI сервисов",
    "интеграция CRM ERP 1C",
    "автоматизация бизнес процессов",
  ],
});

export default function CustomAIPage() {
  return <ServiceDetailPage service={service} />;
}
