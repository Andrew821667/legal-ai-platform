import { NextRequest, NextResponse } from "next/server";

import { checkLawyerAccess, checkLawyerSessionCookie, parseAllowedIds } from "./lawyer-access";
import { TELEGRAM_INIT_DATA_HEADER } from "./telegram-webapp-auth";

/**
 * HTTP-обёртка над проверкой доступа к рабочему месту юриста.
 *
 * Отдельно от verifyMiniAppRequest намеренно. У той проверки есть послабления
 * (MINIAPP_ALLOW_UNVERIFIED, отключаемое требование авторизации), после которых
 * запрос проходит с неизвестным пользователем. Для клиентских экранов это
 * приемлемо: там личность — удобство, а данные и так принадлежат смотрящему.
 *
 * Здесь наоборот: экран показывает обращения, документы и договоры всех
 * клиентов практики. Послабление, включённое когда-то ради отладки, открыло бы
 * это посторонним. Поэтому подпись обязательна всегда.
 *
 * Два независимых пути входа. Внутри Telegram initData есть всегда — это
 * основной путь, строгий и без послаблений. Вне Telegram (иконка на экране
 * iPhone, обычная вкладка Safari) initData нет вовсе, и вместо нет остаётся
 * куда более узкая, но настоящая дверь — куки, выданная ботом через
 * /lawyer/login. Куки пробуем, только когда заголовок initData отсутствует
 * целиком: если он есть, но не прошёл проверку, это не повод молча
 * переключаться на запасной путь — это ошибка, о которой надо сказать прямо.
 */

export type LawyerContext = { telegramUserId: number };

export const LAWYER_SESSION_COOKIE = "lawyer_session";

export function allowedLawyerIds(): number[] {
  // ADMIN_TELEGRAM_ID — владелец практики. LAWYER_TELEGRAM_IDS оставлен на
  // случай, когда юристов станет больше одного: список через запятую.
  return parseAllowedIds(process.env.ADMIN_TELEGRAM_ID, process.env.LAWYER_TELEGRAM_IDS);
}

export function lawyerSessionSecret(): string {
  return (process.env.LAWYER_SESSION_SECRET || "").trim();
}

export function requireLawyer(request: NextRequest): LawyerContext | NextResponse {
  const initData = request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "";
  const allowedIds = allowedLawyerIds();

  if (initData.trim()) {
    const result = checkLawyerAccess({
      initData,
      // Мини-апп открывается из бота-ассистента, значит и подпись initData от
      // его токена. READER_BOT_TOKEN здесь не подходит: это другой бот.
      botToken: (process.env.LEAD_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "").trim(),
      allowedIds,
    });
    if (!result.ok) {
      return NextResponse.json({ detail: result.detail }, { status: result.status });
    }
    return { telegramUserId: result.telegramUserId };
  }

  const cookieResult = checkLawyerSessionCookie({
    cookie: request.cookies.get(LAWYER_SESSION_COOKIE)?.value || "",
    secret: lawyerSessionSecret(),
    allowedIds,
  });
  if (!cookieResult.ok) {
    return NextResponse.json({ detail: cookieResult.detail }, { status: cookieResult.status });
  }
  return { telegramUserId: cookieResult.telegramUserId };
}
