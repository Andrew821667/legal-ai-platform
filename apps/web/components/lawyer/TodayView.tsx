"use client";

import { useState } from "react";

import { Card, Pill } from "./ui";
import type { Tone } from "./ui";
import { AGREEMENT_STATUS, OUTREACH_REASON, days, intakeTitle, label, shortDate, shortDay } from "./labels";
import type { Today, TodayItem, TodaySection } from "./types";
import { lawyerAction } from "./useTelegram";
import { formatRub } from "@/lib/money";

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
    case "bot_handoff":
      return item.need ? `${item.need} — ${item.contact || "контакт не указан"}` : item.contact || "контакт не указан";
    case "awaiting_client":
      return `${item.subject} — ${label(AGREEMENT_STATUS, item.status)}${
        item.last_reminded_at ? ` · бот напомнил ${shortDate(item.last_reminded_at)}` : ""
      }`;
    case "expiring":
      return `${item.subject} — действует до ${shortDate(item.expires_at)}`;
    case "deadline_soon":
      return `${intakeTitle({ practice: item.practice, legal_area: item.legal_area || "other", category: item.category })} — до ${shortDay(item.deadline_at)}`;
    case "no_agreement":
      return intakeTitle({ practice: item.practice, legal_area: item.legal_area || "other", category: item.category });
    case "undelivered":
      return `${item.kind_label}: ${item.text || ""}`;
    case "act_claimed_paid":
      return `Акт № ${item.act_number} — ${formatRub(item.amount_minor ?? null)}`;
    case "act_overdue":
      return `Акт № ${item.act_number} — ${formatRub(item.amount_minor ?? null)}${
        item.last_reminded_at ? ` · напоминали ${shortDate(item.last_reminded_at)}` : ""
      }`;
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
  initData = "",
  onChanged,
}: {
  today: Today;
  onOpen: (leadId: string) => void;
  initData?: string;
  /** После «Повторить» или «Скрыть» — перечитать задачи. */
  onChanged?: () => void;
}) {
  const sections = today.sections.filter((s) => s.items.length > 0);
  const total = sections.reduce((sum, s) => sum + s.items.length, 0);

  if (total === 0) {
    return (
      <Card className="text-center">
        <p className="text-lw-lg font-medium text-lw-ink">Ничего не ждёт</p>
        <p className="mt-1 text-lw-base text-lw-muted">
          Все договоры отправлены, вопросы отвечены, обращения в работе.
        </p>
        <p className="mt-3 text-lw-sm text-lw-muted">
          Здесь только то, что стоит из-за вас. Все клиенты — на соседней вкладке.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-lw-sm text-lw-muted">
        Здесь только то, что стоит из-за вас — {total}. Полный список клиентов на
        соседней вкладке.
      </p>

      {sections.map((section) => (
        <section key={section.key} className="lw-card p-4">
          <h2 className="text-lw-lg font-bold text-lw-ink">{section.title}</h2>
          <p className="mt-0.5 text-lw-sm text-lw-muted">{section.hint}</p>

          <ul className="mt-3 space-y-2">
            {section.items.map((item, index) => (
              <li key={`${section.key}-${item.agreement_id || item.intake_id || index}`}>
                <button
                  type="button"
                  disabled={!item.lead_id}
                  onClick={() => item.lead_id && onOpen(item.lead_id)}
                  className="w-full rounded-xl bg-lw-cell p-3 text-left transition-colors hover:bg-lw-blue-soft disabled:cursor-default disabled:opacity-70"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 text-lw-base font-medium text-lw-ink">
                      {item.client}
                      {item.is_test ? <span className="ml-2 align-middle"><Pill tone="mute">Тест</Pill></span> : null}
                    </span>
                    {(() => {
                      const badge = itemBadge(item);
                      return badge ? <Pill tone={badge.tone}>{badge.text}</Pill> : null;
                    })()}
                  </div>
                  <p className="mt-1 line-clamp-2 text-lw-sm text-lw-muted">
                    {itemLine(section, item)}
                  </p>
                  {section.key === "undelivered" && item.last_error ? (
                    <p className="mt-1 line-clamp-1 text-lw-sm text-lw-danger">
                      {item.delivery_status === "pending" ? "Повторяется: " : "Не ушло: "}
                      {item.last_error}
                    </p>
                  ) : null}
                </button>
                {section.key === "undelivered" && item.delivery_id ? (
                  <DeliveryActions item={item} initData={initData} onChanged={onChanged} />
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

/**
 * «Повторить» — только для уведомлений: договор, ответ и акт отправляют из
 * карточки, чтобы клиент не получил дубль того, что уже отправлено заново.
 */
function DeliveryActions({
  item,
  initData,
  onChanged,
}: {
  item: TodayItem;
  initData: string;
  onChanged?: () => void;
}) {
  const [busy, setBusy] = useState<"retry" | "dismiss" | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const run = async (action: "retry" | "dismiss") => {
    setBusy(action);
    setNote(null);
    try {
      const result = await lawyerAction<{ status?: string }>(
        `/api/lawyer/deliveries/${item.delivery_id}/${action}`,
        initData,
      );
      if (action === "retry" && result.status !== "sent") setNote("Не ушло и сейчас — повторится само.");
      onChanged?.();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не получилось");
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-2 px-1">
      {item.retryable ? (
        <button type="button" disabled={busy !== null} onClick={() => run("retry")} className="lw-btn-quiet !px-3 !py-1.5 !text-lw-sm">
          {busy === "retry" ? "Отправляю…" : "Повторить"}
        </button>
      ) : item.lead_id ? (
        <span className="text-lw-sm text-lw-muted">Отправьте заново из карточки клиента.</span>
      ) : null}
      <button type="button" disabled={busy !== null} onClick={() => run("dismiss")} className="text-lw-sm text-lw-muted underline underline-offset-2 hover:text-lw-primary">
        {busy === "dismiss" ? "Скрываю…" : "Скрыть"}
      </button>
      {note ? <span className="text-lw-sm text-lw-danger">{note}</span> : null}
    </div>
  );
}
