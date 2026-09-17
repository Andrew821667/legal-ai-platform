/**
 * Поля, которыми личный кабинет (/cabinet) дополняет обычную форму «Передать
 * задачу» — framework-free ради тестируемости: /api/leads/route.ts читает и
 * проверяет куку client_session сам, сюда передаёт уже верифицированный
 * результат (или null для анонимного посетителя сайта, как было раньше).
 *
 * Клиент никогда не передаёт telegram_user_id сам — только сервер, из куки:
 * иначе форма могла бы приписать заявку чужому аккаунту.
 */

export type CabinetLeadSession = { telegramUserId: number } | null;

export function cabinetLeadFields(session: CabinetLeadSession): { telegram_user_id?: number } {
  return session ? { telegram_user_id: session.telegramUserId } : {};
}

/** source_context у обычной формы — адрес страницы (для аналитики landing).
 * Из кабинета адрес всегда /cabinet и ничего не говорит про то, откуда
 * человек когда-то пришёл на сайт — вместо этого пишем осмысленную метку. */
export function cabinetSourceContext(session: CabinetLeadSession, fallback: string): string {
  return session ? "cabinet" : fallback;
}

/** Доп. пометки в notes — видны юристу в карточке лида. */
export function cabinetNoteTags(session: CabinetLeadSession): string[] {
  return session ? ["channel=cabinet", "telegram_verified=1"] : [];
}
