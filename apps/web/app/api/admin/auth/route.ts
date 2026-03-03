import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

function safeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

export async function POST(request: NextRequest) {
  const configuredPassword = process.env.ADMIN_PANEL_PASSWORD || "";

  if (!configuredPassword) {
    return NextResponse.json(
      { detail: "ADMIN_PANEL_PASSWORD не настроен на сервере" },
      { status: 500 },
    );
  }

  let payload: { password?: string };
  try {
    payload = (await request.json()) as { password?: string };
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const password = typeof payload.password === "string" ? payload.password : "";
  if (!password) {
    return NextResponse.json({ detail: "Пароль не передан" }, { status: 400 });
  }

  if (!safeEqual(password, configuredPassword)) {
    return NextResponse.json({ detail: "Неверный пароль" }, { status: 401 });
  }

  return NextResponse.json({ ok: true }, { status: 200 });
}
