import { clientCorePost } from "@/lib/client-core";
import { BOOKING_TOKEN } from "@/lib/consultation";

/** Клиент сообщает об оплате — юрист сверит поступление. */

export const dynamic = "force-dynamic";

export async function POST(_request: Request, ctx: { params: Promise<{ token: string }> }) {
  const { token } = await ctx.params;
  if (!BOOKING_TOKEN.test(token)) return Response.json({ detail: "Запись не найдена." }, { status: 404 });
  return clientCorePost(`/api/v1/consultations/bookings/${token}/claim`, {});
}
