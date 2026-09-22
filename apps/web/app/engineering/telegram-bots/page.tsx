import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["telegram-bots"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: ROUTES.telegramBots,
  socialImage: "/engineering/opengraph-image",
  keywords: [
    "разработка Telegram бота",
    "Telegram бот для бизнеса",
    "заказать Telegram бота",
    "Telegram бот с CRM",
    "AI бот для бизнеса",
    "автоматизация заявок Telegram",
  ],
});

export default function TelegramBotsPage() {
  return <ServiceDetailPage service={service} path={ROUTES.telegramBots} />;
}
