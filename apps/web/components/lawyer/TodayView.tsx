"use client";

import { Card, Pill } from "./ui";
import type { Tone } from "./ui";
import { AGREEMENT_STATUS, AREA, OUTREACH_REASON, days, label, shortDate } from "./labels";
import type { Today, TodayItem, TodaySection } from "./types";

/**
 * Экран «Сегодня» отвечает на один вопрос: что стоит без движения из-за меня.
 *
 * Пустые разделы не показываются. Список из пяти заголовков, под четырьмя из
 * которых написано «ничего нет», читается как отчёт, а не как список дел.
 */

function itemLine(section: TodaySection, item: TodayItem): string {
  switch (section.key) {
    case "draft_not_sent":
      return `${item.subject} — ${item.price_text}`;
    case "client_question":
      return item.question || "";
    case "unreachable":
      return `${item.contact || "контакт не указан"} — ${label(OUTREACH_REASON, item.reason)}`;
    case "awaiting_client":
      return `${item.subject} — ${label(AGREEMENT_STATUS, item.status)}`;
    case "expiring":
      return `${item.subject} — действует до ${shortDate(item.expires_at)}`;
    case "no_agreement":
      return label(AREA, item.legal_area);
    default:
      return "";
  }
}

/**
 * Отметка срочности справа от имени.
 *
 * Для сгорающего предложения счётчик идёт в обратную сторону: там важно не
 * сколько уже ждут, а сколько осталось — и «просрочено» здесь не оттенок
 * смысла, а другая задача.
 */
function itemBadge(item: TodayItem): { text: string; tone: Tone } | null {
  if (item.days_left !== undefined && item.days_left !== null) {
    if (item.days_left < 0) return { text: "просрочено", tone: "alert" };
    if (item.days_left === 0) return { text: "сегодня", tone: "alert" };
    return { text: `осталось ${days(item.days_left)}`, tone: "warn" };
  }
  if (item.days_waiting) {
    return { text: days(item.days_waiting), tone: item.days_waiting >= 3 ? "alert" : "warn" };
  }
  return null;
}

export default function TodayView({
  today,
  onOpen,
}: {
  today: Today;
  onOpen: (leadId: string) => void;
}) {
  const sections = today.sections.filter((s) => s.items.length > 0);
  const total = sections.reduce((sum, s) => sum + s.items.length, 0);

  if (total === 0) {
    return (
      <Card className="text-center">
        <p className="text-lg font-medium text-white">Ничего не ждёт</p>
        <p className="mt-1 text-base text-slate-400">
          Все договоры отправлены, вопросы отвечены, обращения в работе.
        </p>
        <p className="mt-3 text-sm text-slate-600">
          Здесь только то, что стоит из-за вас. Все клиенты — на соседней вкладке.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Здесь только то, что стоит из-за вас — {total}. Полный список клиентов на
        соседней вкладке.
      </p>

      {sections.map((section) => (
        <section key={section.key} className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4">
          <h2 className="text-base font-semibold text-white">{section.title}</h2>
          <p className="mt-0.5 text-sm text-slate-500">{section.hint}</p>

          <ul className="mt-3 space-y-2">
            {section.items.map((item, index) => (
              <li key={`${section.key}-${item.agreement_id || item.intake_id || index}`}>
                <button
                  type="button"
                  disabled={!item.lead_id}
                  onClick={() => item.lead_id && onOpen(item.lead_id)}
                  className="w-full rounded-xl bg-slate-800/70 p-3 text-left transition-colors hover:bg-slate-800 disabled:cursor-default disabled:opacity-70"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 text-base font-medium text-white">{item.client}</span>
                    {(() => {
                      const badge = itemBadge(item);
                      return badge ? <Pill tone={badge.tone}>{badge.text}</Pill> : null;
                    })()}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-slate-400">
                    {itemLine(section, item)}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
