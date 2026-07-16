import { NextRequest, NextResponse } from "next/server";

import { requireAdminSession } from "@/lib/admin-session";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://localhost:8000";
const CORE_API_ADMIN_KEY = process.env.CORE_API_ADMIN_KEY || process.env.API_KEY_ADMIN || "";

async function callCore(path: string, init?: RequestInit) {
  if (!CORE_API_ADMIN_KEY) {
    return NextResponse.json({ detail: "Core API admin key is not configured" }, { status: 500 });
  }
  const response = await fetch(`${CORE_API_URL.replace(/\/+$/, "")}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CORE_API_ADMIN_KEY,
      ...(init?.headers || {}),
    },
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  const raw = await response.text();
  let data: unknown = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw ? { detail: raw } : {};
  }
  return { response, data };
}

export async function GET(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) return unauthorized;

  try {
    const status = request.nextUrl.searchParams.get("status");
    const params = new URLSearchParams({ limit: "200" });
    if (status) params.set("status_filter", status);
    const result = await callCore(`/api/v1/legal-intakes?${params.toString()}`);
    if (result instanceof NextResponse) return result;
    if (!result.response.ok) {
      return NextResponse.json(result.data, { status: result.response.status });
    }
    return NextResponse.json({ intakes: result.data });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : "Failed to load legal intakes";
    return NextResponse.json({ detail }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) return unauthorized;

  try {
    const payload = (await request.json()) as Record<string, unknown>;
    const id = typeof payload.id === "string" ? payload.id.trim() : "";
    if (!id) return NextResponse.json({ detail: "id is required" }, { status: 400 });

    const body = {
      status: payload.status,
      conflict_status: payload.conflict_status,
      assigned_to: payload.assigned_to,
      internal_note: payload.internal_note,
    };
    const result = await callCore(`/api/v1/legal-intakes/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    if (result instanceof NextResponse) return result;
    if (!result.response.ok) {
      return NextResponse.json(result.data, { status: result.response.status });
    }
    return NextResponse.json({ intake: result.data });
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : "Failed to update legal intake";
    return NextResponse.json({ detail }, { status: 500 });
  }
}
