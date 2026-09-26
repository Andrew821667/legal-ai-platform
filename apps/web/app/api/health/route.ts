/**
 * Живы ли сайт и ядро за ним — для внешнего мониторинга (.github/workflows/uptime.yml).
 *
 * Mac mini стоит дома: пропал свет или интернет — сайт и боты лежат, и никто
 * не узнаёт. Проверка снаружи смотрит сюда. Ничего, кроме «да/нет», не
 * отдаёт: адрес ядра, версии и ошибки наружу не нужны.
 */

export const dynamic = "force-dynamic";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";

export async function GET() {
  let core = false;
  try {
    const response = await fetch(`${CORE_API_URL}/health`, { cache: "no-store", signal: AbortSignal.timeout(5_000) });
    core = response.ok;
  } catch {
    core = false;
  }
  return Response.json(
    { ok: core, web: true, core },
    { status: core ? 200 : 503, headers: { "cache-control": "no-store" } },
  );
}
