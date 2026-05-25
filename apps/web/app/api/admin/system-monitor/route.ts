import tls from "node:tls";

import { NextRequest, NextResponse } from "next/server";

import { requireAdminSession } from "@/lib/admin-session";

export const runtime = "nodejs";

const CORE_API_URL = process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://localhost:8000";
const CORE_API_ADMIN_KEY = process.env.CORE_API_ADMIN_KEY || process.env.API_KEY_ADMIN || "";
const SITE_PUBLIC_URL = process.env.NEXT_PUBLIC_SITE_URL || process.env.SITE_PUBLIC_URL || "";
const CONTRACT_AI_SYSTEM_URL = process.env.NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL || "https://contract.ai-verdict.ru";
const SITE_INTERNAL_CHECK_URL = process.env.SITE_INTERNAL_CHECK_URL || "";
const CONTRACT_AI_INTERNAL_CHECK_URL = process.env.CONTRACT_AI_INTERNAL_CHECK_URL || "";
const TELEGRAM_API_HOST = process.env.TELEGRAM_API_HOST || "api.telegram.org";
const ARCHIVED_PUBLICATION_ERROR_PREFIXES = [
  "deleted_irrelevant",
  "expired_review_cleanup",
  "expired_editorial_cleanup",
  "expired_weekly_review_cleanup",
];

type CheckStatus = "ok" | "warn" | "error" | "unknown";

type EndpointCheck = {
  name: string;
  status: CheckStatus;
  url?: string;
  statusCode?: number;
  latencyMs?: number;
  detail?: string;
};

function nowIso(): string {
  return new Date().toISOString();
}

function elapsedMs(startedAt: number): number {
  return Math.round(performance.now() - startedAt);
}

function publicSiteBaseUrl(): string {
  const configured = SITE_PUBLIC_URL.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  const domain = String(process.env.DOMAIN || "ai-verdict.ru").trim();
  return `https://${domain}`.replace(/\/+$/, "");
}

function normalizeBaseUrl(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "";
  }
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  return withScheme.replace(/\/+$/, "");
}

function internalSiteBaseUrl(): string {
  return normalizeBaseUrl(SITE_INTERNAL_CHECK_URL) || "http://127.0.0.1:3000";
}

function internalContractBaseUrl(): string {
  const configured = normalizeBaseUrl(CONTRACT_AI_INTERNAL_CHECK_URL);
  if (configured) {
    return configured;
  }
  return normalizeBaseUrl(process.env.CONTRACT_AI_UPSTREAM || "") || "http://host.docker.internal:3000";
}

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

function normalizeStatus(ok: boolean, warn = false): CheckStatus {
  if (!ok) {
    return "error";
  }
  return warn ? "warn" : "ok";
}

async function fetchJson(path: string, init?: RequestInit): Promise<{ ok: boolean; status: number; data: any; latencyMs: number }> {
  const startedAt = performance.now();
  const response = await fetch(`${CORE_API_URL.replace(/\/+$/, "")}${path}`, {
    ...init,
    headers: {
      "X-API-Key": CORE_API_ADMIN_KEY,
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
    signal: AbortSignal.timeout(8_000),
  });

  const raw = await response.text();
  let data: any = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw ? { detail: raw } : {};
  }

  return {
    ok: response.ok,
    status: response.status,
    data,
    latencyMs: elapsedMs(startedAt),
  };
}

async function safeCoreJson(path: string): Promise<{ ok: boolean; status: number; data: any; latencyMs: number; error?: string }> {
  try {
    return await fetchJson(path);
  } catch (error: any) {
    return {
      ok: false,
      status: 0,
      data: null,
      latencyMs: 0,
      error: error?.message || "request failed",
    };
  }
}

async function checkUrl(name: string, url: string, probeUrl = url): Promise<EndpointCheck> {
  const startedAt = performance.now();
  try {
    const response = await fetch(probeUrl, {
      method: "GET",
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(8_000),
    });
    const ok = response.status >= 200 && response.status < 400;
    return {
      name,
      url,
      status: normalizeStatus(ok, response.status >= 300),
      statusCode: response.status,
      latencyMs: elapsedMs(startedAt),
      detail: probeUrl === url ? undefined : `probe: ${probeUrl}`,
    };
  } catch (error: any) {
    return {
      name,
      url,
      status: "error",
      latencyMs: elapsedMs(startedAt),
      detail: error?.message || "request failed",
    };
  }
}

async function checkTelegramTls(): Promise<EndpointCheck> {
  const startedAt = performance.now();
  return new Promise((resolve) => {
    const socket = tls.connect({
      host: TELEGRAM_API_HOST,
      port: 443,
      servername: TELEGRAM_API_HOST,
      timeout: 8_000,
    });

    const finish = (check: EndpointCheck) => {
      socket.destroy();
      resolve(check);
    };

    socket.once("secureConnect", () => {
      finish({
        name: "Telegram API TLS",
        status: "ok",
        url: `tls://${TELEGRAM_API_HOST}:443`,
        latencyMs: elapsedMs(startedAt),
        detail: socket.getProtocol() || "TLS connected",
      });
    });
    socket.once("timeout", () => {
      finish({
        name: "Telegram API TLS",
        status: "error",
        url: `tls://${TELEGRAM_API_HOST}:443`,
        latencyMs: elapsedMs(startedAt),
        detail: "TLS timeout",
      });
    });
    socket.once("error", (error) => {
      finish({
        name: "Telegram API TLS",
        status: "error",
        url: `tls://${TELEGRAM_API_HOST}:443`,
        latencyMs: elapsedMs(startedAt),
        detail: error.message,
      });
    });
  });
}

function countStatuses(rows: any[]): Record<string, number> {
  return rows.reduce<Record<string, number>>((acc, item) => {
    const status = String(item?.status || "unknown");
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});
}

function isArchivedPublicationFailure(row: any): boolean {
  const lastError = String(row?.last_error || "").trim().toLowerCase();
  return ARCHIVED_PUBLICATION_ERROR_PREFIXES.some((prefix) => lastError.startsWith(prefix));
}

function buildIssues(input: {
  coreHealth: Awaited<ReturnType<typeof safeCoreJson>>;
  detailedHealth: Awaited<ReturnType<typeof safeCoreJson>>;
  workersStatus: Awaited<ReturnType<typeof safeCoreJson>>;
  scheduledCounts: Record<string, number>;
  dueCount: number;
  stalePublishingCount: number;
  contractSummary: any;
  endpoints: EndpointCheck[];
}): string[] {
  const issues: string[] = [];
  if (!input.coreHealth.ok) {
    issues.push("core_health_unavailable");
  }
  if (!input.detailedHealth.ok) {
    issues.push("core_detailed_health_unavailable");
  }

  const workerRows = Array.isArray(input.workersStatus.data?.workers) ? input.workersStatus.data.workers : [];
  const criticalWorkers = ["news-generate", "news-telegram-ingest", "news-publish", "news-reader-digest"];
  const workerMap = new Map<string, any>(workerRows.map((row: any) => [String(row.worker_id || ""), row]));
  for (const workerId of criticalWorkers) {
    const row = workerMap.get(workerId);
    if (!row) {
      issues.push(`worker_missing:${workerId}`);
    } else if (!row.active) {
      issues.push(`worker_inactive:${workerId}`);
    }
  }

  if (input.dueCount > 0) {
    issues.push(`due_posts:${input.dueCount}`);
  }
  if (input.stalePublishingCount > 0) {
    issues.push(`stale_publishing:${input.stalePublishingCount}`);
  }
  if ((input.scheduledCounts.failed || 0) > 0) {
    issues.push(`failed_posts:${input.scheduledCounts.failed}`);
  }
  if (Number(input.contractSummary?.processing_stale_count || 0) > 0) {
    issues.push(`contract_stale_processing:${input.contractSummary.processing_stale_count}`);
  }
  if (Number(input.contractSummary?.failed_retryable_count || 0) > 0) {
    issues.push(`contract_failed_retryable:${input.contractSummary.failed_retryable_count}`);
  }

  for (const endpoint of input.endpoints) {
    if (endpoint.status === "error") {
      issues.push(`endpoint_error:${endpoint.name}`);
    }
  }

  return issues;
}

export async function GET(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) {
    return unauthorized;
  }
  if (!CORE_API_ADMIN_KEY) {
    return NextResponse.json(
      { detail: "CORE_API_ADMIN_KEY or API_KEY_ADMIN is not configured on web server" },
      { status: 500 },
    );
  }

  const siteBaseUrl = publicSiteBaseUrl();
  const siteProbeBaseUrl = internalSiteBaseUrl();
  const contractProbeBaseUrl = internalContractBaseUrl();
  const [
    coreHealth,
    detailedHealth,
    workersStatus,
    contractSummary,
    readerFunnel,
    readerSummary,
    reviewPosts,
    scheduledPosts,
    duePosts,
    failedPosts,
    publishingPosts,
    postedPosts,
    telegramTls,
    homeCheck,
    miniappCheck,
    miniappContentCheck,
    contractCheck,
  ] = await Promise.all([
    safeCoreJson("/health"),
    safeCoreJson("/health/detailed"),
    safeCoreJson("/api/v1/workers/status"),
    safeCoreJson("/api/v1/contract-jobs/summary?window_hours=24&stale_minutes=30"),
    safeCoreJson("/api/v1/scheduled-posts/feedback/reader-funnel?days=7"),
    safeCoreJson("/api/v1/scheduled-posts/feedback/reader-summary?days=7"),
    safeCoreJson("/api/v1/scheduled-posts?status=review&limit=100&newest_first=true"),
    safeCoreJson("/api/v1/scheduled-posts?status=scheduled&limit=100"),
    safeCoreJson("/api/v1/scheduled-posts?due=true&limit=100"),
    safeCoreJson("/api/v1/scheduled-posts?status=failed&limit=100&newest_first=true"),
    safeCoreJson("/api/v1/scheduled-posts?status=publishing&limit=100"),
    safeCoreJson("/api/v1/scheduled-posts?status=posted&limit=20&newest_first=true"),
    checkTelegramTls(),
    checkUrl("Сайт", `${siteBaseUrl}/`, `${siteProbeBaseUrl}/`),
    checkUrl("Mini App", `${siteBaseUrl}/miniapp`, joinUrl(siteProbeBaseUrl, "/miniapp")),
    checkUrl("Mini App content", `${siteBaseUrl}/miniapp/content`, joinUrl(siteProbeBaseUrl, "/miniapp/content")),
    checkUrl("Contract AI System", CONTRACT_AI_SYSTEM_URL, `${contractProbeBaseUrl}/`),
  ]);

  const failedRows = Array.isArray(failedPosts.data) ? failedPosts.data : [];
  const actionableFailedRows = failedRows.filter((row: any) => !isArchivedPublicationFailure(row));
  const archivedFailedRows = failedRows.filter(isArchivedPublicationFailure);
  const postRows = [
    ...(Array.isArray(reviewPosts.data) ? reviewPosts.data : []),
    ...(Array.isArray(scheduledPosts.data) ? scheduledPosts.data : []),
    ...actionableFailedRows,
    ...(Array.isArray(publishingPosts.data) ? publishingPosts.data : []),
    ...(Array.isArray(postedPosts.data) ? postedPosts.data : []),
  ];
  const scheduledCounts = countStatuses(postRows);
  const dueCount = Array.isArray(duePosts.data) ? duePosts.data.length : 0;
  const publishingRows = Array.isArray(publishingPosts.data) ? publishingPosts.data : [];
  const stalePublishingCount = publishingRows.filter((post: any) => {
    const updatedAt = Date.parse(String(post?.updated_at || post?.publish_at || ""));
    return Number.isFinite(updatedAt) && Date.now() - updatedAt > 15 * 60 * 1000;
  }).length;
  const endpoints = [telegramTls, homeCheck, miniappCheck, miniappContentCheck, contractCheck];
  const issues = buildIssues({
    coreHealth,
    detailedHealth,
    workersStatus,
    scheduledCounts,
    dueCount,
    stalePublishingCount,
    contractSummary: contractSummary.data,
    endpoints,
  });

  return NextResponse.json({
    generated_at: nowIso(),
    status: issues.some((issue) => issue.includes("unavailable") || issue.includes("endpoint_error")) ? "error" : issues.length ? "warn" : "ok",
    issues,
    core: {
      base_url: CORE_API_URL,
      health: coreHealth,
      detailed_health: detailedHealth,
    },
    workers: workersStatus.data || { workers: [] },
    contracts: {
      summary: contractSummary.data,
    },
    publications: {
      counts: scheduledCounts,
      due_count: dueCount,
      stale_publishing_count: stalePublishingCount,
      archived_failed_cleanup_count: archivedFailedRows.length,
      review: Array.isArray(reviewPosts.data) ? reviewPosts.data.slice(0, 10) : [],
      scheduled: Array.isArray(scheduledPosts.data) ? scheduledPosts.data.slice(0, 10) : [],
      failed: actionableFailedRows.slice(0, 10),
      archived_failed_cleanup: archivedFailedRows.slice(0, 10),
      recent_posted: Array.isArray(postedPosts.data) ? postedPosts.data.slice(0, 10) : [],
    },
    reader: {
      funnel: readerFunnel.data,
      summary: readerSummary.data,
    },
    endpoints,
    raw: {
      coreHealth,
      detailedHealth,
      workersStatus,
      contractSummary,
      readerFunnel,
      readerSummary,
    },
  });
}
