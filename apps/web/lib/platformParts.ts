import {
  AppWindow,
  FileCheck2,
  Globe,
  MessageCircle,
  Newspaper,
  type LucideIcon,
} from "lucide-react";

import { EXTERNAL_LINKS, ROUTES } from "@/lib/links";

/**
 * Single source of truth for the user-facing "parts of the AI Verdict platform".
 *
 * Used in three places (so a single edit propagates):
 *  - the home page (full-size grid, "platform map" section);
 *  - the Mini App home (compact grid, "other entry points");
 *  - the site footer (link-list "Platform" column).
 *
 * The lead-bot `/start` handler also reuses these (id, name, url) — kept in
 * sync manually because the bot is a separate Python service. If you change
 * the list here, update apps/lead-bot/lead_bot/run.py:_PLATFORM_PARTS too.
 */

export type PlatformPartId =
  | "site"
  | "contract"
  | "lead_bot"
  | "news"
  | "miniapp";

export type PlatformPart = {
  id: PlatformPartId;
  name: string;
  /** One-or-two sentence description shown on cards. */
  description: string;
  /** URL to open. May be an external https URL or an internal route. */
  url: string;
  /** True when url leaves the current host (opens in a new tab). */
  external: boolean;
  /** Short CTA label for the card primary action. */
  ctaLabel: string;
  /** Lucide icon for the card header. */
  icon: LucideIcon;
  /**
   * Optional secondary CTA (e.g. News card showing both channel and bot).
   * Same shape as the primary fields.
   */
  secondary?: {
    label: string;
    url: string;
    external: boolean;
  };
};

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ai-verdict.ru";

export const PLATFORM_PARTS: PlatformPart[] = [
  {
    id: "site",
    name: "Сайт AI Verdict",
    description:
      "Обзор продуктов, юридической автоматизации, интеграций, прикладной разработки и заявка на консультацию.",
    url: ROUTES.home,
    external: false,
    ctaLabel: "Открыть сайт",
    icon: Globe,
  },
  {
    id: "contract",
    name: "Contract AI System",
    description:
      "Флагман платформы: проверка договора, выявление рисков, рекомендации по правкам.",
    url: EXTERNAL_LINKS.contractAI || ROUTES.contractAI,
    external: Boolean(EXTERNAL_LINKS.contractAI),
    ctaLabel: "Открыть Contract AI",
    icon: FileCheck2,
  },
  {
    id: "lead_bot",
    name: "Ассистент в Telegram",
    description:
      "Диалоговый бот: задать вопрос, получить демо, оставить заявку на legal tech, интеграцию, бота, сайт или внутренний сервис.",
    url: EXTERNAL_LINKS.leadBot,
    external: true,
    ctaLabel: "Открыть бота",
    icon: MessageCircle,
  },
  {
    id: "news",
    name: "Новостной контур",
    description:
      "Канал с разборами AI-новостей в legal-сфере и бот-ридер с персональным фидом.",
    url: EXTERNAL_LINKS.channel,
    external: true,
    ctaLabel: "Подписаться на канал",
    icon: Newspaper,
    secondary: {
      label: "Открыть reader-бота",
      url: EXTERNAL_LINKS.readerBot,
      external: true,
    },
  },
  {
    id: "miniapp",
    name: "Mini App",
    description:
      "Личный контур внутри Telegram: контент, инструменты, профиль и заявка на юридическую или смежную автоматизацию.",
    url: ROUTES.miniApp,
    external: false,
    ctaLabel: "Открыть Mini App",
    icon: AppWindow,
  },
];

/** Lookup by id; throws if missing (so a typo at the call site fails loud). */
export function getPlatformPart(id: PlatformPartId): PlatformPart {
  const found = PLATFORM_PARTS.find((part) => part.id === id);
  if (!found) {
    throw new Error(`Unknown platform part id: ${id}`);
  }
  return found;
}

/** Shorter URL for footer / bot — strips https:// for display. */
export function displayUrl(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

/** Absolute URL used by the lead-bot when it doesn't know the request host. */
export function platformAbsoluteUrl(part: PlatformPart): string {
  if (part.external || /^https?:\/\//i.test(part.url)) {
    return part.url;
  }
  return `${SITE_URL.replace(/\/$/, "")}${part.url}`;
}
