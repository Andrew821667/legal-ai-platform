import { NextRequest, NextResponse } from "next/server";

import { checkLawyerAccess, parseAllowedIds } from "./lawyer-access";
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
 */

export type LawyerContext = { telegramUserId: number };

export function allowedLawyerIds(): number[] {
  // ADMIN_TELEGRAM_ID — владелец практики. LAWYER_TELEGRAM_IDS оставлен на
  // случай, когда юристов станет больше одного: список через запятую.
  return parseAllowedIds(process.env.ADMIN_TELEGRAM_ID, process.env.LAWYER_TELEGRAM_IDS);
}

export function requireLawyer(request: NextRequest): LawyerContext | NextResponse {
  const result = checkLawyerAccess({
    initData: request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "",
    // Мини-апп открывается из бота-ассистента, значит и подпись initData от его
    // токена. READER_BOT_TOKEN здесь не подходит: это другой бот.
    botToken: (process.env.LEAD_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "").trim(),
    allowedIds: allowedLawyerIds(),
  });

  if (!result.ok) {
    return NextResponse.json({ detail: result.detail }, { status: result.status });
  }
  return { telegramUserId: result.telegramUserId };
}
