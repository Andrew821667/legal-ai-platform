export const ROUTES = {
  home: "/",
  forLawyers: "/for-lawyers",
  forBusiness: "/for-business",
  contractAI: "/contract-ai-system",
  solutions: "/solutions",
  contentCases: "/content-cases",
  about: "/about",
  miniApp: "/miniapp",
  miniAppContent: "/miniapp/content",
  miniAppTools: "/miniapp/tools",
  miniAppSolutions: "/miniapp/solutions",
  miniAppProfile: "/miniapp/profile",
} as const;

const LEAD_BOT_USERNAME = "legal_ai_helper_new_bot";
const READER_BOT_USERNAME = "legal_ai_news_reader_bot";
const CHANNEL_USERNAME = "legal_ai_pro";
const CONTRACT_AI_SYSTEM_URL = (process.env.NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL || "").trim();

export const EXTERNAL_LINKS = {
  leadBot: `https://t.me/${LEAD_BOT_USERNAME}`,
  readerBot: `https://t.me/${READER_BOT_USERNAME}`,
  channel: `https://t.me/${CHANNEL_USERNAME}`,
  contractAI: CONTRACT_AI_SYSTEM_URL,
} as const;

function appendHash(href: string, hash?: string): string {
  if (!hash) {
    return href;
  }
  const normalized = hash.startsWith("#") ? hash : `#${hash}`;
  return `${href}${normalized}`;
}

export function contractAIEntryHref(hash?: string): string {
  const base = EXTERNAL_LINKS.contractAI || ROUTES.contractAI;
  return appendHash(base, hash);
}

export function contractAIEntryIsExternal(): boolean {
  return Boolean(EXTERNAL_LINKS.contractAI);
}

export function leadBotDeepLink(start?: string): string {
  if (!start) {
    return EXTERNAL_LINKS.leadBot;
  }

  return `${EXTERNAL_LINKS.leadBot}?start=${encodeURIComponent(start)}`;
}

export type ReaderBotStartSection =
  | "discover"
  | "validate"
  | "solutions"
  | "profile"
  | "search"
  | "miniapp_content"
  | "miniapp_tools"
  | "miniapp_solutions"
  | "miniapp_profile";

export function readerBotDeepLink(start?: ReaderBotStartSection): string {
  if (!start) {
    return EXTERNAL_LINKS.readerBot;
  }

  return `${EXTERNAL_LINKS.readerBot}?start=${encodeURIComponent(start)}`;
}
