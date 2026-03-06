export const ROUTES = {
  home: "/",
  forLawyers: "/for-lawyers",
  forBusiness: "/for-business",
  contractAI: "/contract-ai-system",
  solutions: "/solutions",
  contentCases: "/content-cases",
  about: "/about",
} as const;

const LEAD_BOT_USERNAME = "legal_ai_helper_new_bot";
const CHANNEL_USERNAME = "legal_ai_pro";

export const EXTERNAL_LINKS = {
  leadBot: `https://t.me/${LEAD_BOT_USERNAME}`,
  channel: `https://t.me/${CHANNEL_USERNAME}`,
} as const;

export function leadBotDeepLink(start?: string): string {
  if (!start) {
    return EXTERNAL_LINKS.leadBot;
  }

  return `${EXTERNAL_LINKS.leadBot}?start=${encodeURIComponent(start)}`;
}
