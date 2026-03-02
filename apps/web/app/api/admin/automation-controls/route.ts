import { NextRequest, NextResponse } from 'next/server';

const CORE_API_URL = process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || 'http://localhost:8000';
const CORE_API_ADMIN_KEY = process.env.CORE_API_ADMIN_KEY || process.env.API_KEY_ADMIN || '';

async function callCore(path: string, init?: RequestInit) {
  if (!CORE_API_ADMIN_KEY) {
    return NextResponse.json(
      { detail: 'CORE_API_ADMIN_KEY or API_KEY_ADMIN is not configured on web server' },
      { status: 500 },
    );
  }

  const response = await fetch(`${CORE_API_URL}${path}`, {
    ...init,
    headers: {
      'X-API-Key': CORE_API_ADMIN_KEY,
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });

  const raw = await response.text();
  let data: any = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw ? { detail: raw } : {};
  }
  return { response, data };
}

export async function GET(request: NextRequest) {
  try {
    await callCore('/api/v1/automation-controls/bootstrap', { method: 'POST' });

    const scope = request.nextUrl.searchParams.get('scope');
    const params = scope ? `?scope=${encodeURIComponent(scope)}` : '';
    const result = await callCore(`/api/v1/automation-controls${params}`);
    if (result instanceof NextResponse) {
      return result;
    }
    if (!result.response.ok) {
      return NextResponse.json(result.data, { status: result.response.status });
    }
    return NextResponse.json({ controls: result.data });
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || 'Failed to load automation controls' },
      { status: 500 },
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const payload = await request.json();
    const key = String(payload?.key || '').trim();
    if (!key) {
      return NextResponse.json({ detail: 'key is required' }, { status: 400 });
    }

    const result = await callCore(`/api/v1/automation-controls/${encodeURIComponent(key)}`, {
      method: 'PUT',
      body: JSON.stringify({
        scope: payload.scope ?? null,
        title: payload.title,
        description: payload.description,
        enabled: payload.enabled,
        config: payload.config,
      }),
    });
    if (result instanceof NextResponse) {
      return result;
    }
    if (!result.response.ok) {
      return NextResponse.json(result.data, { status: result.response.status });
    }
    return NextResponse.json({ control: result.data });
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || 'Failed to update automation control' },
      { status: 500 },
    );
  }
}
