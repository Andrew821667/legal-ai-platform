import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["custom-ai"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: ROUTES.engineering,
  keywords: [
    "разработка программного обеспечения",
    "разработка Telegram ботов",
    "разработка Mini App",
    "разработка AI сервисов",
    "интеграция CRM ERP 1C",
    "автоматизация бизнес процессов",
  ],
});

export default function EngineeringPage() {
  return <ServiceDetailPage service={service} path={ROUTES.engineering} />;
}
