/**
 * Этап дела одной фразой — та же лестница, что считает ядро (_stage_for в
 * lawyer_workspace.py), но для одного обращения.
 *
 * Ядро отдаёт этап на клиента целиком, по последнему договору. Пока у
 * клиента одно дело, это одно и то же. У постоянного клиента с двумя
 * параллельными обращениями шкала в шапке показывала бы ход только одного из
 * них — поэтому у каждого обращения своя, по его договорам.
 */

export function stageFor(ndaSigned: boolean, agreementStatus: string | null | undefined): string {
  if (agreementStatus === "signed") return "Договор подписан";
  if (agreementStatus === "sent" || agreementStatus === "viewed") return "Договор у клиента";
  if (agreementStatus === "draft") return "Договор не отправлен";
  if (agreementStatus === "declined") return "Клиент отказался";
  if (ndaSigned) return "Готовим условия";
  return "Первичное обращение";
}

/** Договоры обращения приходят новыми вперёд — этап по первому из них. */
export function matterStage(
  agreements: { status: string; created_at: string | null }[],
  ndaSigned: boolean,
): string {
  const latest = [...agreements].sort((a, b) =>
    String(b.created_at || "").localeCompare(String(a.created_at || "")),
  )[0];
  return stageFor(ndaSigned, latest?.status ?? null);
}
