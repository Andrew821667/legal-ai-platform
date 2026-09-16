/**
 * Разбор запроса на связь обращения с делом другого клиента.
 *
 * Отдельно от маршрута, чтобы проверить без Next: идентификаторы уходят в
 * путь и тело запроса к ядру, и произвольную строку туда пропускать нельзя.
 */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ROLES = new Set(["main", "subordinate", "joint"]);

export type IntakeLinkPayload = {
  linked_lead_id: string;
  linked_intake_id?: string;
  role: string;
  note?: string;
};

export function parseIntakeLinkPayload(
  body: unknown,
): { ok: true; payload: IntakeLinkPayload } | { ok: false; error: string } {
  const raw = (body && typeof body === "object" ? body : {}) as Record<string, unknown>;
  const linkedLeadId = String(raw.linked_lead_id ?? "");
  if (!UUID.test(linkedLeadId)) {
    return { ok: false, error: "Некорректный идентификатор клиента" };
  }
  const role = String(raw.role ?? "");
  if (!ROLES.has(role)) {
    return { ok: false, error: "Неизвестная роль связи" };
  }
  const payload: IntakeLinkPayload = { linked_lead_id: linkedLeadId, role };
  // Конкретное дело обязательно только когда у клиента их несколько — это
  // решает ядро (409), здесь лишь не пропускаем мусор.
  if (raw.linked_intake_id !== undefined && raw.linked_intake_id !== null && raw.linked_intake_id !== "") {
    const linkedIntakeId = String(raw.linked_intake_id);
    if (!UUID.test(linkedIntakeId)) {
      return { ok: false, error: "Некорректный идентификатор обращения" };
    }
    payload.linked_intake_id = linkedIntakeId;
  }
  const note = typeof raw.note === "string" ? raw.note.trim().slice(0, 500) : "";
  if (note) payload.note = note;
  return { ok: true, payload };
}
