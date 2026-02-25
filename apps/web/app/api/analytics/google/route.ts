import { NextResponse } from 'next/server';

/**
 * API endpoint для получения данных из Google Analytics 4
 *
 * Требуемые переменные окружения:
 * - GA4_PROPERTY_ID: ID свойства GA4 (например: "123456789")
 * - GA4_CREDENTIALS: JSON строка с credentials от Service Account
 *   или можно использовать отдельный файл ga4-credentials.json
 */

const GA4_PROPERTY_ID = process.env.GA4_PROPERTY_ID;
const GA4_CREDENTIALS = process.env.GA4_CREDENTIALS;

interface GA4MetricData {
  today: {
    visits: number;
    pageviews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgDuration: string;
    conversions: number;
  };
  week: {
    visits: number;
    pageviews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgDuration: string;
    conversions: number;
  };
  month: {
    visits: number;
    pageviews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgDuration: string;
    conversions: number;
  };
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

/**
 * Форматирование секунд в формат MM:SS
 */
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Получение данных из Google Analytics 4 Data API
 */
async function fetchGA4Data(): Promise<GA4MetricData | null> {
  if (!GA4_PROPERTY_ID || !GA4_CREDENTIALS) {
    console.warn('GA4 credentials not configured');
    return null;
  }

  try {
    // Парсим credentials
    const credentials = JSON.parse(GA4_CREDENTIALS);

    // Получаем access token через Service Account
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        assertion: await createJWT(credentials),
      }),
    });

    if (!tokenResponse.ok) {
      throw new Error(`Failed to get access token: ${tokenResponse.status}`);
    }

    const { access_token } = await tokenResponse.json();

    // Запрашиваем данные из GA4 Data API
    const [todayData, weekData, monthData, topPagesData, sourcesData] = await Promise.all([
      runGA4Report(access_token, 'today', ['sessions', 'screenPageViews', 'totalUsers', 'bounceRate', 'averageSessionDuration', 'conversions']),
      runGA4Report(access_token, '7daysAgo', ['sessions', 'screenPageViews', 'totalUsers', 'bounceRate', 'averageSessionDuration', 'conversions']),
      runGA4Report(access_token, '30daysAgo', ['sessions', 'screenPageViews', 'totalUsers', 'bounceRate', 'averageSessionDuration', 'conversions']),
      runGA4Report(access_token, '30daysAgo', ['screenPageViews'], ['pagePath']),
      runGA4Report(access_token, '30daysAgo', ['sessions'], ['sessionSource']),
    ]);

    return {
      today: parseMetrics(todayData),
      week: parseMetrics(weekData),
      month: parseMetrics(monthData),
      topPages: parseTopPages(topPagesData),
      sources: parseSources(sourcesData),
    };

  } catch (error) {
    console.error('Error fetching GA4 data:', error);
    return null;
  }
}

/**
 * Создание JWT для Service Account
 */
async function createJWT(credentials: any): Promise<string> {
  // Для production используйте библиотеку jsonwebtoken или jose
  // Это упрощенная версия, в реальности нужна правильная подпись
  const header = {
    alg: 'RS256',
    typ: 'JWT',
  };

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: credentials.client_email,
    scope: 'https://www.googleapis.com/auth/analytics.readonly',
    aud: 'https://oauth2.googleapis.com/token',
    exp: now + 3600,
    iat: now,
  };

  // В production используйте crypto.sign() или библиотеку для JWT
  throw new Error('JWT signing not implemented - use proper JWT library in production');
}

/**
 * Запрос отчета из GA4 Data API
 */
async function runGA4Report(
  accessToken: string,
  dateRange: string,
  metrics: string[],
  dimensions: string[] = []
): Promise<any> {
  const response = await fetch(
    `https://analyticsdata.googleapis.com/v1beta/properties/${GA4_PROPERTY_ID}:runReport`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        dateRanges: [{ startDate: dateRange, endDate: 'today' }],
        metrics: metrics.map(m => ({ name: m })),
        dimensions: dimensions.map(d => ({ name: d })),
      }),
      next: { revalidate: 300 }, // Кэш на 5 минут
    }
  );

  if (!response.ok) {
    throw new Error(`GA4 API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Парсинг метрик из ответа GA4
 */
function parseMetrics(data: any) {
  const row = data.rows?.[0]?.metricValues || [];

  return {
    visits: parseInt(row[0]?.value || '0'),
    pageviews: parseInt(row[1]?.value || '0'),
    uniqueVisitors: parseInt(row[2]?.value || '0'),
    bounceRate: parseFloat(row[3]?.value || '0'),
    avgDuration: formatDuration(parseFloat(row[4]?.value || '0')),
    conversions: parseInt(row[5]?.value || '0'),
  };
}

/**
 * Парсинг топ страниц
 */
function parseTopPages(data: any) {
  return (data.rows || []).slice(0, 5).map((row: any) => ({
    page: row.dimensionValues[0]?.value || '/',
    visits: parseInt(row.metricValues[0]?.value || '0'),
    avgTime: '0:00', // Для получения времени нужен дополнительный запрос
  }));
}

/**
 * Парсинг источников трафика
 */
function parseSources(data: any) {
  const total = (data.rows || []).reduce(
    (sum: number, row: any) => sum + parseInt(row.metricValues[0]?.value || '0'),
    0
  );

  return (data.rows || []).slice(0, 4).map((row: any) => {
    const sessions = parseInt(row.metricValues[0]?.value || '0');
    return {
      name: row.dimensionValues[0]?.value || 'Unknown',
      percentage: total > 0 ? Math.round((sessions / total) * 100 * 10) / 10 : 0,
    };
  });
}

/**
 * Mock данные для демонстрации (когда GA4 не настроен)
 */
function getMockGA4Data(): GA4MetricData {
  return {
    today: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0,
    },
    week: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0,
    },
    month: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0,
    },
    topPages: [],
    sources: [],
  };
}

export async function GET() {
  try {
    const data = await fetchGA4Data();

    return NextResponse.json({
      success: !!data,
      source: 'google-analytics-4',
      configured: !!(GA4_PROPERTY_ID && GA4_CREDENTIALS),
      data: data || getMockGA4Data(),
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('GA4 API Route Error:', error);
    return NextResponse.json(
      {
        success: false,
        source: 'google-analytics-4',
        configured: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        data: getMockGA4Data(),
      },
      { status: 500 }
    );
  }
}
