import { createSign } from "node:crypto";

const GA4_PROPERTY_ID = (process.env.GA4_PROPERTY_ID || "").trim();
const GA4_CREDENTIALS = (process.env.GA4_CREDENTIALS || "").trim();
const GA4_TOKEN_URL_DEFAULT = "https://oauth2.googleapis.com/token";

type MetricPeriod = {
  visits: number;
  pageviews: number;
  uniqueVisitors: number;
  bounceRate: number;
  avgDuration: string;
  conversions: number;
};

export interface GA4MetricData {
  today: MetricPeriod;
  week: MetricPeriod;
  month: MetricPeriod;
  topPages: Array<{
    page: string;
    visits: number;
    avgTime: string;
  }>;
  sources: Array<{
    name: string;
    percentage: number;
  }>;
}

type ServiceAccountCredentials = {
  client_email?: string;
  private_key?: string;
  token_uri?: string;
};

type AnalyticsPayload = {
  success: boolean;
  source: "google-analytics-4";
  configured: boolean;
  data: GA4MetricData;
  timestamp: string;
  error?: string;
};

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function toBase64Url(input: Buffer | string): string {
  return Buffer.from(input)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function parseCredentials(raw: string): ServiceAccountCredentials | null {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as ServiceAccountCredentials;
    const email = String(parsed.client_email || "").trim();
    const privateKey = String(parsed.private_key || "").trim();
    if (!email || !privateKey) {
      return null;
    }
    return {
      client_email: email,
      private_key: privateKey,
      token_uri: String(parsed.token_uri || "").trim() || GA4_TOKEN_URL_DEFAULT,
    };
  } catch {
    return null;
  }
}

function buildServiceAccountJwt(credentials: ServiceAccountCredentials): string {
  const now = Math.floor(Date.now() / 1000);
  const header = {
    alg: "RS256",
    typ: "JWT",
  };
  const payload = {
    iss: credentials.client_email,
    scope: "https://www.googleapis.com/auth/analytics.readonly",
    aud: credentials.token_uri || GA4_TOKEN_URL_DEFAULT,
    exp: now + 3600,
    iat: now,
  };

  const encodedHeader = toBase64Url(JSON.stringify(header));
  const encodedPayload = toBase64Url(JSON.stringify(payload));
  const body = `${encodedHeader}.${encodedPayload}`;

  const signer = createSign("RSA-SHA256");
  signer.update(body);
  signer.end();
  const signature = signer.sign(credentials.private_key || "");
  return `${body}.${toBase64Url(signature)}`;
}

async function fetchAccessToken(credentials: ServiceAccountCredentials): Promise<string> {
  const assertion = buildServiceAccountJwt(credentials);
  const tokenUrl = credentials.token_uri || GA4_TOKEN_URL_DEFAULT;
  const tokenResponse = await fetch(tokenUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
    cache: "no-store",
  });

  if (!tokenResponse.ok) {
    const raw = await tokenResponse.text();
    throw new Error(`Failed to get GA4 access token (${tokenResponse.status}): ${raw.slice(0, 200)}`);
  }
  const tokenPayload = (await tokenResponse.json()) as { access_token?: string };
  const accessToken = String(tokenPayload.access_token || "").trim();
  if (!accessToken) {
    throw new Error("GA4 access token is empty");
  }
  return accessToken;
}

async function runGA4Report(
  accessToken: string,
  dateRange: string,
  metrics: string[],
  dimensions: string[] = [],
): Promise<any> {
  const response = await fetch(
    `https://analyticsdata.googleapis.com/v1beta/properties/${GA4_PROPERTY_ID}:runReport`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        dateRanges: [{ startDate: dateRange, endDate: "today" }],
        metrics: metrics.map((metric) => ({ name: metric })),
        dimensions: dimensions.map((dimension) => ({ name: dimension })),
      }),
      cache: "no-store",
    },
  );

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`GA4 API error (${response.status}): ${raw.slice(0, 200)}`);
  }
  return response.json();
}

function parseMetrics(data: any): MetricPeriod {
  const row = data?.rows?.[0]?.metricValues || [];
  return {
    visits: parseInt(row[0]?.value || "0", 10),
    pageviews: parseInt(row[1]?.value || "0", 10),
    uniqueVisitors: parseInt(row[2]?.value || "0", 10),
    bounceRate: parseFloat(row[3]?.value || "0"),
    avgDuration: formatDuration(parseFloat(row[4]?.value || "0")),
    conversions: parseInt(row[5]?.value || "0", 10),
  };
}

function parseTopPages(data: any): GA4MetricData["topPages"] {
  return (data?.rows || []).slice(0, 5).map((row: any) => ({
    page: row?.dimensionValues?.[0]?.value || "/",
    visits: parseInt(row?.metricValues?.[0]?.value || "0", 10),
    avgTime: "0:00",
  }));
}

function parseSources(data: any): GA4MetricData["sources"] {
  const rows = data?.rows || [];
  const total = rows.reduce(
    (sum: number, row: any) => sum + parseInt(row?.metricValues?.[0]?.value || "0", 10),
    0,
  );

  return rows.slice(0, 4).map((row: any) => {
    const sessions = parseInt(row?.metricValues?.[0]?.value || "0", 10);
    return {
      name: row?.dimensionValues?.[0]?.value || "Unknown",
      percentage: total > 0 ? Math.round((sessions / total) * 100 * 10) / 10 : 0,
    };
  });
}

function getMockGA4Data(): GA4MetricData {
  return {
    today: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: "0:00",
      conversions: 0,
    },
    week: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: "0:00",
      conversions: 0,
    },
    month: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: "0:00",
      conversions: 0,
    },
    topPages: [],
    sources: [],
  };
}

async function fetchGA4Data(): Promise<GA4MetricData | null> {
  if (!GA4_PROPERTY_ID || !GA4_CREDENTIALS) {
    return null;
  }

  const credentials = parseCredentials(GA4_CREDENTIALS);
  if (!credentials) {
    throw new Error("GA4_CREDENTIALS is invalid or missing required fields");
  }

  const accessToken = await fetchAccessToken(credentials);
  const [todayData, weekData, monthData, topPagesData, sourcesData] = await Promise.all([
    runGA4Report(
      accessToken,
      "today",
      ["sessions", "screenPageViews", "totalUsers", "bounceRate", "averageSessionDuration", "conversions"],
    ),
    runGA4Report(
      accessToken,
      "7daysAgo",
      ["sessions", "screenPageViews", "totalUsers", "bounceRate", "averageSessionDuration", "conversions"],
    ),
    runGA4Report(
      accessToken,
      "30daysAgo",
      ["sessions", "screenPageViews", "totalUsers", "bounceRate", "averageSessionDuration", "conversions"],
    ),
    runGA4Report(accessToken, "30daysAgo", ["screenPageViews"], ["pagePath"]),
    runGA4Report(accessToken, "30daysAgo", ["sessions"], ["sessionSource"]),
  ]);

  return {
    today: parseMetrics(todayData),
    week: parseMetrics(weekData),
    month: parseMetrics(monthData),
    topPages: parseTopPages(topPagesData),
    sources: parseSources(sourcesData),
  };
}

export async function loadGoogleAnalyticsPayload(): Promise<AnalyticsPayload> {
  const timestamp = new Date().toISOString();
  const configured = Boolean(GA4_PROPERTY_ID && GA4_CREDENTIALS);
  try {
    const data = await fetchGA4Data();
    return {
      success: Boolean(data),
      source: "google-analytics-4",
      configured,
      data: data || getMockGA4Data(),
      timestamp,
    };
  } catch (error) {
    return {
      success: false,
      source: "google-analytics-4",
      configured,
      data: getMockGA4Data(),
      timestamp,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
