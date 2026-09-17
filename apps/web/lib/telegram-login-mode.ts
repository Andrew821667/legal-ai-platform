export type TelegramLoginMode = "oidc" | "legacy";

/**
 * oidc (по умолчанию) — Authorization Code + PKCE через oauth.telegram.org.
 * legacy — iframe-виджет telegram-widget.js, запасной вариант на случай,
 * если Login Widget недоступен в @BotFather для этого бота (нужен
 * /setdomain вместо Allowed URLs). Единственное место, читающее эту
 * переменную из процесса, — дальше режим передаётся параметром.
 */
export function telegramLoginMode(): TelegramLoginMode {
  return process.env.TELEGRAM_LOGIN_MODE === "legacy" ? "legacy" : "oidc";
}
