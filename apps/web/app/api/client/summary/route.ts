import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientCoreGet } from "@/lib/client-core";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  return clientCoreGet(`/api/v1/client-portal/summary?telegram_user_id=${auth.telegramUserId}`);
}
