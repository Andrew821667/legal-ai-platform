export const ROUTES = {
  home: "/",
  forLawyers: "/for-lawyers",
  legalAi: "/legal-ai",
  forBusiness: "/for-business",
  contractAI: "/contract-ai-system",
  solutions: "/solutions",
  contentCases: "/content-cases",
  aiLaw: "/ai-law",
  legalHelp: "/legal-help",
  engineering: "/engineering",
  legalHelpBusiness: "/legal-help/business",
  legalHelpIndividuals: "/legal-help/individuals",
  about: "/about",
  miniApp: "/miniapp",
  miniAppContent: "/miniapp/content",
  miniAppTools: "/miniapp/tools",
  miniAppSolutions: "/miniapp/solutions",
  miniAppProfile: "/miniapp/profile",
  miniAppLead: "/miniapp/lead",
  miniAppLegalHelp: "/miniapp/legal-help",
} as const;

const LEAD_BOT_USERNAME = (process.env.NEXT_PUBLIC_LEAD_BOT_USERNAME || "legal_ai_helper_new_bot").trim();
const READER_BOT_USERNAME = (process.env.NEXT_PUBLIC_READER_BOT_USERNAME || "legal_ai_news_reader_bot").trim();
const CHANNEL_USERNAME = (process.env.NEXT_PUBLIC_CHANNEL_USERNAME || "ai_verdict").trim();
const DEFAULT_CONTRACT_AI_SYSTEM_URL = "https://contract.ai-verdict.ru";
const CONTRACT_AI_SYSTEM_URL = (
  process.env.NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL || DEFAULT_CONTRACT_AI_SYSTEM_URL
).trim();
const CORE_API_URL = (process.env.NEXT_PUBLIC_CORE_API_URL || "").trim();

export const EXTERNAL_LINKS = {
  leadBot: `https://t.me/${LEAD_BOT_USERNAME}`,
  readerBot: `https://t.me/${READER_BOT_USERNAME}`,
  channel: `https://t.me/${CHANNEL_USERNAME}`,
  contractAI: CONTRACT_AI_SYSTEM_URL,
  githubProfile: "https://github.com/Andrew821667",
  githubPlatform: "https://github.com/Andrew821667/legal-ai-platform",
  githubContractAI: "https://github.com/Andrew821667/Contract-AI-System-",
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

/**
 * URL для SSO-входа в Contract-AI-System через core-api proxy.
 * core-api получает SSO-токен от Contract-AI-System и возвращает redirect_url.
 */
export function contractAISsoUrl(): string {
  return CORE_API_URL ? `${CORE_API_URL}/api/v1/contract-ai/sso` : "";
}

/**
 * URL для проверки статуса Contract-AI-System.
 */
export function contractAIStatusUrl(): string {
  return CORE_API_URL ? `${CORE_API_URL}/api/v1/contract-ai/status` : "";
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
