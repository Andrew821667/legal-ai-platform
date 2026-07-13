export const VISUAL_THEME =
  process.env.NEXT_PUBLIC_AI_VERDICT_VISUAL_THEME === "legacy-dark"
    ? "legacy-dark"
    : "light-ops";

export const isLightOpsTheme = VISUAL_THEME === "light-ops";
