import { clientCoreGet } from "@/lib/client-core";

/** Свободное время для записи на консультацию и её цена — публично. */

export const dynamic = "force-dynamic";

export async function GET() {
  return clientCoreGet("/api/v1/consultations/slots");
}
