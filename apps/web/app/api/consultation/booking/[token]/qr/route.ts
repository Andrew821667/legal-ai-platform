import { clientCoreGetFile } from "@/lib/client-core";
import { BOOKING_TOKEN } from "@/lib/consultation";

/** Платёжный QR брони — ядро само откажет, если оплата уже подтверждена. */

export const dynamic = "force-dynamic";

export async function GET(_request: Request, ctx: { params: Promise<{ token: string }> }) {
  const { token } = await ctx.params;
  if (!BOOKING_TOKEN.test(token)) return Response.json({ detail: "Запись не найдена." }, { status: 404 });
  return clientCoreGetFile(`/api/v1/consultations/bookings/${token}/payment-qr`);
}
