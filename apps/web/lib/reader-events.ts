export const MINIAPP_EVENT_TYPES = {
  action: "action",
  navClick: "nav_click",
  ctaClick: "cta_click",
  profileSaved: "profile_saved",
  contentOpen: "content_open",
  toolOpen: "tool_open",
  solutionOpen: "solution_open",
  deeplinkOpen: "deeplink_open",
  deeplinkIssued: "deeplink_issued",
} as const;

export const MINIAPP_EVENT_SOURCES = {
  app: "miniapp.app",
  topbar: "miniapp.topbar",
  home: "miniapp.home",
  content: "miniapp.content",
  tools: "miniapp.tools",
  solutions: "miniapp.solutions",
  profile: "miniapp.profile",
  flow: "miniapp.flow",
  deeplink: "miniapp.deeplink",
  readerBot: "reader.bot",
  readerStart: "reader.start",
  readerNav: "reader.nav",
  readerDiscover: "reader.discover",
  readerValidate: "reader.validate",
  readerSolutions: "reader.solutions",
  readerProfile: "reader.profile",
  readerCommand: "reader.command",
  readerArticle: "reader.article",
  readerPost: "reader.post",
} as const;

export const MINIAPP_SCREENS = {
  home: "/miniapp",
  content: "/miniapp/content",
  tools: "/miniapp/tools",
  solutions: "/miniapp/solutions",
  profile: "/miniapp/profile",
} as const;

export const MINIAPP_ACTIONS = {
  openContent: "open.content",
  openContentItem: "open.content_item",
  openContractAI: "open.contract_ai",
  openSolutions: "open.solutions",
  openRecommendedStep: "open.recommended_step",
  openOnboarding: "open.onboarding",
  openProfile: "open.profile",
  openHistory: "open.history",
  openFutureTools: "open.future_tools",
  openSolutionsForLawyers: "open.solutions.for_lawyers",
  openSolutionsForBusiness: "open.solutions.for_business",
  openSolutionsRoadmap: "open.solutions.roadmap",
  flowDiscover: "flow.discover",
  flowValidate: "flow.validate",
  flowImplement: "flow.implement",
  profileSaved: "profile.saved",
  openAssistant: "cta.open.assistant",
  openMiniAppHome: "open.miniapp.home",
  openMiniAppContent: "open.miniapp.content",
  openMiniAppTools: "open.miniapp.tools",
  openMiniAppSolutions: "open.miniapp.solutions",
  openMiniAppProfile: "open.miniapp.profile",
  openMiniAppResume: "open.miniapp.resume",
} as const;

export type MiniAppEventType = (typeof MINIAPP_EVENT_TYPES)[keyof typeof MINIAPP_EVENT_TYPES];
export type MiniAppEventSource = (typeof MINIAPP_EVENT_SOURCES)[keyof typeof MINIAPP_EVENT_SOURCES];
export type MiniAppScreen = (typeof MINIAPP_SCREENS)[keyof typeof MINIAPP_SCREENS];
export type MiniAppAction = (typeof MINIAPP_ACTIONS)[keyof typeof MINIAPP_ACTIONS];

export function resolveMiniAppScreen(value: string): MiniAppScreen {
  const input = (value || "").trim().toLowerCase();
  if (input === MINIAPP_SCREENS.home || input === "home" || input === "miniapp") {
    return MINIAPP_SCREENS.home;
  }
  if (input === MINIAPP_SCREENS.content || input === "content") {
    return MINIAPP_SCREENS.content;
  }
  if (input === MINIAPP_SCREENS.tools || input === "tools") {
    return MINIAPP_SCREENS.tools;
  }
  if (input === MINIAPP_SCREENS.solutions || input === "solutions") {
    return MINIAPP_SCREENS.solutions;
  }
  if (input === MINIAPP_SCREENS.profile || input === "profile") {
    return MINIAPP_SCREENS.profile;
  }
  return MINIAPP_SCREENS.home;
}

export function defaultActionForScreen(screen: MiniAppScreen): MiniAppAction {
  switch (screen) {
    case MINIAPP_SCREENS.content:
      return MINIAPP_ACTIONS.openMiniAppContent;
    case MINIAPP_SCREENS.tools:
      return MINIAPP_ACTIONS.openMiniAppTools;
    case MINIAPP_SCREENS.solutions:
      return MINIAPP_ACTIONS.openMiniAppSolutions;
    case MINIAPP_SCREENS.profile:
      return MINIAPP_ACTIONS.openMiniAppProfile;
    default:
      return MINIAPP_ACTIONS.openMiniAppHome;
  }
}
