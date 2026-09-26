import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientFields } from "@/lib/client-ref";
import { clientCoreGet, clientCorePost } from "@/lib/client-core";

export async function GET(request: NextRequest) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  return clientCoreGet("/api/v1/nda/document");
}

export async function POST(request: NextRequest) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return Response.json({ detail: "Некорректные данные." }, { status: 400 });
  }
  const data = body as Record<string, unknown>;
  const action = String(data.action || "sign");
  const paths: Record<string, string> = {
    "consent-preview": "/api/v1/nda/personal-data-consent/preview",
    "consent-accept": "/api/v1/nda/personal-data-consent/accept",
    "nda-preview": "/api/v1/nda/document/preview",
    sign: "/api/v1/nda/sign",
  };
  const path = paths[action];
  if (!path) {
    return Response.json({ detail: "Некорректное действие." }, { status: 400 });
  }
  const { action: _, ...payload } = data;
  return clientCorePost(path, {
    ...payload,
    ...clientFields(auth),
    channel: "miniapp",
  });
}
