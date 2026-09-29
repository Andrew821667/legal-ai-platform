/**
 * Идёт ли такт ядра — для внешнего мониторинга (.github/workflows/uptime.yml).
 *
 * Такт (напоминания клиентам, сводка, проверка бэкапа, обезличивание) дёргает
 * бот; если бот перестал, сайт работает, а эти задачи молча стоят. Наружу —
 * только «да/нет», как и /api/health.
 */

export const dynamic = "force-dynamic";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";

export async function GET() {
  let ok = false;
  try {
    const response = await fetch(`${CORE_API_URL}/health/tick`, { cache: "no-store", signal: AbortSignal.timeout(5_000) });
    ok = response.ok;
  } catch {
    ok = false;
  }
  return Response.json({ ok }, { status: ok ? 200 : 503, headers: { "cache-control": "no-store" } });
}
