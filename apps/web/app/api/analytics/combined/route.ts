import { NextResponse } from 'next/server';

/**
 * API endpoint для получения объединенных данных из Google Analytics 4 и Yandex Metrika
 *
 * Этот endpoint комбинирует данные из обеих систем аналитики
 * и предоставляет единый интерфейс для админ-панели.
 */

interface AnalyticsData {
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
 * Получение данных из обеих систем аналитики
 */
async function fetchCombinedAnalytics(): Promise<{
  ga4: any;
  yandex: any;
  combined: AnalyticsData;
  sources: string[];
}> {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

  try {
    // Запрашиваем данные из обеих систем параллельно
    const [ga4Response, yandexResponse] = await Promise.allSettled([
      fetch(`${baseUrl}/api/analytics/google`, {
        next: { revalidate: 300 },
      }),
      fetch(`${baseUrl}/api/analytics/yandex`, {
        next: { revalidate: 300 },
      }),
    ]);

    // Получаем данные или используем fallback
    const ga4Data =
      ga4Response.status === 'fulfilled' && ga4Response.value.ok
        ? await ga4Response.value.json()
        : { success: false, data: null };

    const yandexData =
      yandexResponse.status === 'fulfilled' && yandexResponse.value.ok
        ? await yandexResponse.value.json()
        : { success: false, data: null };

    // Определяем какие источники доступны
    const sources: string[] = [];
    if (ga4Data.configured && ga4Data.success) sources.push('Google Analytics 4');
    if (yandexData.configured && yandexData.success) sources.push('Yandex Metrika');

    // Комбинируем данные
    const combined = combineData(ga4Data.data, yandexData.data, sources);

    return {
      ga4: ga4Data,
      yandex: yandexData,
      combined,
      sources,
    };
  } catch (error) {
    console.error('Error fetching combined analytics:', error);
    throw error;
  }
}

/**
 * Комбинирование данных из двух источников
 * Приоритет: Yandex Metrika > Google Analytics 4 (для российской аудитории точнее)
 */
function combineData(
  ga4Data: any,
  yandexData: any,
  sources: string[]
): AnalyticsData {
  // Если есть только один источник - используем его
  if (sources.length === 1) {
    if (sources.includes('Yandex Metrika') && yandexData) {
      return yandexData;
    }
    if (sources.includes('Google Analytics 4') && ga4Data) {
      return ga4Data;
    }
  }

  // Если оба источника доступны - приоритет Yandex Metrika, но добавляем данные GA4
  if (sources.length === 2 && ga4Data && yandexData) {
    return {
      today: mergeMetrics(yandexData.today, ga4Data.today),
      week: mergeMetrics(yandexData.week, ga4Data.week),
      month: mergeMetrics(yandexData.month, ga4Data.month),
      topPages: mergeTopPages(yandexData.topPages, ga4Data.topPages),
      sources: mergeSources(yandexData.sources, ga4Data.sources),
    };
  }

  // Fallback - пустые данные
  return getMockData();
}

/**
 * Объединение метрик из двух источников (среднее значение)
 */
function mergeMetrics(primary: any, secondary: any) {
  if (!primary && !secondary) return getMockData().today;
  if (!secondary) return primary;
  if (!primary) return secondary;

  return {
    visits: Math.round((primary.visits + secondary.visits) / 2),
    pageviews: Math.round((primary.pageviews + secondary.pageviews) / 2),
    uniqueVisitors: Math.round(
      (primary.uniqueVisitors + secondary.uniqueVisitors) / 2
    ),
    bounceRate: Math.round(((primary.bounceRate + secondary.bounceRate) / 2) * 10) / 10,
    avgDuration: primary.avgDuration, // Используем primary (Yandex Metrika)
    conversions: Math.round((primary.conversions + secondary.conversions) / 2),
  };
}

/**
 * Объединение топ страниц
 */
function mergeTopPages(primary: any[], secondary: any[]) {
  if (!primary || !primary.length) return secondary || [];
  if (!secondary || !secondary.length) return primary || [];

  // Создаем Map для объединения по URL
  const pagesMap = new Map();

  [...primary, ...secondary].forEach((page) => {
    if (pagesMap.has(page.page)) {
      const existing = pagesMap.get(page.page);
      pagesMap.set(page.page, {
        page: page.page,
        visits: Math.round((existing.visits + page.visits) / 2),
        avgTime: existing.avgTime, // Используем первое значение
      });
    } else {
      pagesMap.set(page.page, page);
    }
  });

  // Сортируем по визитам и берем топ 5
  return Array.from(pagesMap.values())
    .sort((a, b) => b.visits - a.visits)
    .slice(0, 5);
}

/**
 * Объединение источников трафика
 */
function mergeSources(primary: any[], secondary: any[]) {
  if (!primary || !primary.length) return secondary || [];
  if (!secondary || !secondary.length) return primary || [];

  // Создаем Map для объединения по имени источника
  const sourcesMap = new Map();

  [...primary, ...secondary].forEach((source) => {
    if (sourcesMap.has(source.name)) {
      const existing = sourcesMap.get(source.name);
      sourcesMap.set(source.name, {
        name: source.name,
        percentage: Math.round(((existing.percentage + source.percentage) / 2) * 10) / 10,
      });
    } else {
      sourcesMap.set(source.name, source);
    }
  });

  // Сортируем по проценту и нормализуем чтобы сумма была 100%
  const sorted = Array.from(sourcesMap.values())
    .sort((a, b) => b.percentage - a.percentage)
    .slice(0, 4);

  const total = sorted.reduce((sum, s) => sum + s.percentage, 0);
  if (total > 0) {
    sorted.forEach((s) => {
      s.percentage = Math.round((s.percentage / total) * 100 * 10) / 10;
    });
  }

  return sorted;
}

/**
 * Mock данные для демонстрации
 */
function getMockData(): AnalyticsData {
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
    const result = await fetchCombinedAnalytics();

    return NextResponse.json({
      success: result.sources.length > 0,
      sources: result.sources,
      data: result.combined,
      raw: {
        ga4: result.ga4,
        yandex: result.yandex,
      },
      timestamp: new Date().toISOString(),
      note:
        result.sources.length === 0
          ? 'No analytics configured. Please set up Google Analytics 4 or Yandex Metrika.'
          : undefined,
    });
  } catch (error) {
    console.error('Combined Analytics API Route Error:', error);
    return NextResponse.json(
      {
        success: false,
        sources: [],
        error: error instanceof Error ? error.message : 'Unknown error',
        data: getMockData(),
      },
      { status: 500 }
    );
  }
}
