"use client";

import { Card, Pill } from "./ui";
import { AGREEMENT_STATUS, AREA, OUTREACH_REASON, days, label } from "./labels";
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
    case "no_agreement":
      return label(AREA, item.legal_area);
    default:
      return "";
  }
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
        <p className="text-base font-medium text-white">Ничего не ждёт</p>
        <p className="mt-1 text-sm text-slate-400">
          Все договоры отправлены, вопросы отвечены, обращения в работе.
        </p>
        <p className="mt-3 text-xs text-slate-600">
          Здесь только то, что стоит из-за вас. Все клиенты — на соседней вкладке.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Здесь только то, что стоит из-за вас — {total}. Полный список клиентов на
        соседней вкладке.
      </p>

      {sections.map((section) => (
        <section key={section.key} className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4">
          <h2 className="text-sm font-semibold text-white">{section.title}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{section.hint}</p>

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
                    <span className="text-sm font-medium text-white">{item.client}</span>
                    {item.days_waiting ? (
                      <Pill tone={item.days_waiting >= 3 ? "alert" : "warn"}>
                        {days(item.days_waiting)}
                      </Pill>
                    ) : null}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-slate-400">
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
