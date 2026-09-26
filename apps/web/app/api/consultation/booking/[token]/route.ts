import { clientCoreGet } from "@/lib/client-core";
import { BOOKING_TOKEN } from "@/lib/consultation";

/** Бронь по её ключу: время, статус, сумма, код платежа. Ключ знает только клиент. */

export const dynamic = "force-dynamic";

export async function GET(_request: Request, ctx: { params: Promise<{ token: string }> }) {
  const { token } = await ctx.params;
  if (!BOOKING_TOKEN.test(token)) return Response.json({ detail: "Запись не найдена." }, { status: 404 });
  return clientCoreGet(`/api/v1/consultations/bookings/${token}`);
}
