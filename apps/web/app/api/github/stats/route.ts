import { NextRequest, NextResponse } from 'next/server';

import { requireAdminSession } from '@/lib/admin-session';

const GITHUB_API = 'https://api.github.com';
const OWNER = 'Andrew821667';
const REPO = 'legal-ai-website';

// GitHub token из переменных окружения (опционально для приватных репозиториев)
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '';

// Хелпер для GitHub API запросов
async function fetchGitHub(endpoint: string) {
  const headers: Record<string, string> = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };

  if (GITHUB_TOKEN) {
    headers['Authorization'] = `Bearer ${GITHUB_TOKEN}`;
  }

  const response = await fetch(`${GITHUB_API}${endpoint}`, {
    headers,
    next: { revalidate: 300 } // Кэш на 5 минут
  });

  if (!response.ok) {
    console.error(`GitHub API Error: ${response.status} ${response.statusText}`);
    return null;
  }

  return response.json();
}

export async function GET(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  try {
    // Получаем данные параллельно
    const [workflowRuns, issues, seoIssues] = await Promise.all([
      // Последние 10 workflow runs
      fetchGitHub(`/repos/${OWNER}/${REPO}/actions/runs?per_page=10`),

      // Все открытые issues
      fetchGitHub(`/repos/${OWNER}/${REPO}/issues?state=all&per_page=100`),

      // SEO issues специально
      fetchGitHub(`/repos/${OWNER}/${REPO}/issues?labels=seo&state=all&per_page=50`)
    ]);

    // Обработка workflow runs
    const workflows = workflowRuns?.workflow_runs?.map((run: any) => ({
      id: run.id,
      name: run.name,
      status: run.status,
      conclusion: run.conclusion,
      created_at: run.created_at,
      updated_at: run.updated_at,
      html_url: run.html_url,
      run_number: run.run_number
    })) || [];

    // Найдем последний SEO Analysis run (самый свежий)
    const seoRuns = workflows
      .filter((w: any) => w.name === 'Automatic SEO Analysis')
      .sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    const lastSeoRun = seoRuns[0] || null;

    // Обработка issues
    const allIssues = issues || [];
    const seoIssuesList = seoIssues || [];

    // Статистика по issues
    const issuesStats = {
      total: allIssues.length,
      open: allIssues.filter((i: any) => i.state === 'open').length,
      closed: allIssues.filter((i: any) => i.state === 'closed').length,

      // SEO issues
      seo_total: seoIssuesList.length,
      seo_open: seoIssuesList.filter((i: any) => i.state === 'open').length,
      seo_closed: seoIssuesList.filter((i: any) => i.state === 'closed').length,

      // По приоритетам
      seo_critical: seoIssuesList.filter((i: any) =>
        i.labels.some((l: any) => l.name === 'seo-critical')
      ).length,
      seo_high: seoIssuesList.filter((i: any) =>
        i.labels.some((l: any) => l.name === 'seo-high')
      ).length,
      seo_medium: seoIssuesList.filter((i: any) =>
        i.labels.some((l: any) => l.name === 'seo-medium')
      ).length
    };

    // Последний SEO отчет (ищем самый свежий issue с меткой 'report')
    const reportIssues = seoIssuesList
      .filter((i: any) => i.labels.some((l: any) => l.name === 'report'))
      .sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const latestSeoReport = reportIssues[0]; // Берем самый свежий

    // Парсим SEO score из title (формат: "📊 SEO Report 2024-01-15 - Score: 85/100")
    let seoScore = null;
    let predictedPosition = null;
    let readability = null;
    let eeatScore = null;

    if (latestSeoReport?.title) {
      const scoreMatch = latestSeoReport.title.match(/Score:\s*(\d+)\/100/);
      if (scoreMatch) {
        seoScore = parseInt(scoreMatch[1]);
      }
    }

    if (latestSeoReport?.body) {
      const posMatch = latestSeoReport.body.match(/\*\*Predicted Position:\*\*\s*([\d.]+)/);
      const readMatch = latestSeoReport.body.match(/\*\*Readability:\*\*\s*([\d.]+)\/100/);
      const eeatMatch = latestSeoReport.body.match(/\*\*E-E-A-T Score:\*\*\s*([\d.]+)\/100/);

      if (posMatch) predictedPosition = parseFloat(posMatch[1]);
      if (readMatch) readability = parseFloat(readMatch[1]);
      if (eeatMatch) eeatScore = parseFloat(eeatMatch[1]);
    }

    // Топ открытых SEO задач (сортируем по приоритету и дате)
    const topSeoTasks = seoIssuesList
      .filter((i: any) => i.state === 'open' && !i.labels.some((l: any) => l.name === 'report'))
      .map((i: any) => ({
        id: i.id,
        number: i.number,
        title: i.title,
        labels: i.labels.map((l: any) => l.name),
        created_at: i.created_at,
        html_url: i.html_url,
        priority: i.labels.some((l: any) => l.name === 'seo-critical') ? 'critical' :
                 i.labels.some((l: any) => l.name === 'seo-high') ? 'high' : 'medium'
      }))
      .sort((a: any, b: any) => {
        // Сначала сортируем по приоритету
        const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2 };
        const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
        if (priorityDiff !== 0) return priorityDiff;

        // Затем по дате создания (новые сначала)
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      })
      .slice(0, 5);

    // Формируем ответ
    const response = {
      timestamp: new Date().toISOString(),

      // Workflow runs
      workflows: {
        recent: workflows.slice(0, 5),
        last_seo_run: lastSeoRun || null,
        total_runs: workflows.length
      },

      // Issues статистика
      issues: issuesStats,

      // SEO отчет
      seo_report: {
        score: seoScore,
        predicted_position: predictedPosition,
        readability: readability,
        eeat_score: eeatScore,
        report_date: latestSeoReport?.created_at || null,
        report_url: latestSeoReport?.html_url || null
      },

      // Топ задачи
      top_seo_tasks: topSeoTasks,

      // История (последние 5 SEO отчетов)
      seo_history: seoIssuesList
        .filter((i: any) => i.labels.some((l: any) => l.name === 'report'))
        .sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 5)
        .map((i: any) => {
          const scoreMatch = i.title.match(/Score:\s*(\d+)\/100/);
          const dateMatch = i.title.match(/(\d{4}-\d{2}-\d{2})/);
          return {
            date: dateMatch ? dateMatch[1] : i.created_at.split('T')[0],
            score: scoreMatch ? parseInt(scoreMatch[1]) : null,
            url: i.html_url
          };
        })
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Error fetching GitHub data:', error);

    // Возвращаем mock данные в случае ошибки
    return NextResponse.json({
      timestamp: new Date().toISOString(),
      error: 'Failed to fetch GitHub data',
      mock: true,
      workflows: {
        recent: [
          {
            id: 1,
            name: 'Automatic SEO Analysis',
            status: 'completed',
            conclusion: 'success',
            created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
            run_number: 42
          }
        ],
        last_seo_run: null,
        total_runs: 1
      },
      issues: {
        total: 15,
        open: 8,
        closed: 7,
        seo_total: 12,
        seo_open: 6,
        seo_closed: 6,
        seo_critical: 2,
        seo_high: 3,
        seo_medium: 1
      },
      seo_report: {
        score: 85,
        predicted_position: 8.5,
        readability: 78,
        eeat_score: 82,
        report_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        report_url: null
      },
      top_seo_tasks: [],
      seo_history: []
    });
  }
}
