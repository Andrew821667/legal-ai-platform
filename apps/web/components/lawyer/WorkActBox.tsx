"use client";

import { useState } from "react";

import ActionButton from "./ActionButton";
import { Pill } from "./ui";
import type { Tone } from "./ui";
import { WORK_ACT_STATUS, label, shortDate } from "./labels";
import { lawyerAction } from "./useTelegram";
import { dropDraft, readDraft, writeDraft } from "./draft-storage";
import { formatRub } from "@/lib/money";
import type { AgreementCard, WorkAct } from "./types";

/**
 * Акты выполненных работ по уже подписанному договору.
 *
 * Договор описывает условия заранее; акт — что фактически сделано и сколько
 * к оплате, обычно после того, как работа закончена. «Оплачено» подтверждает
 * юрист сам: у самозанятого без ИП нет банковского API для автоматической
 * проверки зачислений, а клик клиента «Я оплатил(а)» в Telegram — заявление,
 * не подтверждение.
 */

function actStatusTone(status: string): Tone {
  if (status === "paid") return "ok";
  if (status === "claimed_paid") return "warn";
  return "mute";
}

/**
 * Чек из «Мой налог» по оплаченному акту.
 *
 * Самозанятый обязан передать покупателю чек при расчёте — в том числе
 * ссылкой. Система знала об оплате, но не о чеке, и держалось всё на памяти.
 * Ссылку из приложения «Мой налог» вставляют сюда — и отправляют клиенту.
 */
function ReceiptBox({ act, initData, onChanged }: { act: WorkAct; initData: string; onChanged: () => void }) {
  const [ref, setRef] = useState("");
  const save = (sendToClient: boolean) => async () => {
    await lawyerAction(`/api/lawyer/acts/${act.act_id}/receipt`, initData, {
      ref: ref.trim() || null,
      send_to_client: sendToClient,
    });
    onChanged();
  };

  if (act.receipt_at) {
    const link = act.receipt_ref && /^https:\/\//i.test(act.receipt_ref) ? act.receipt_ref : null;
    return (
      <p className="mt-2 text-lw-sm text-lw-muted">
        Чек выдан {shortDate(act.receipt_at)}
        {link ? (
          <>
            {" · "}
            <a href={link} target="_blank" rel="noreferrer" className="text-lw-primary underline">
              открыть чек
            </a>
          </>
        ) : act.receipt_ref ? (
          ` · № ${act.receipt_ref}`
        ) : null}
        {act.receipt_sent_at ? ` · отправлен клиенту ${shortDate(act.receipt_sent_at)}` : null}
      </p>
    );
  }

  const isLink = /^https:\/\//i.test(ref.trim());
  return (
    <div className="mt-2 rounded-lg bg-lw-warning-soft p-2">
      <p className="text-lw-sm text-lw-warning">Выдайте чек в «Мой налог» и вставьте ссылку на него.</p>
      <input
        value={ref}
        onChange={(event) => setRef(event.target.value)}
        placeholder="https://lknpd.nalog.ru/… или номер чека"
        className="lw-input mt-2 w-full"
        maxLength={500}
      />
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {isLink ? (
          <ActionButton label="Сохранить и отправить клиенту" busy="Отправляю…" done="Чек отправлен" onRun={save(true)} />
        ) : null}
        <ActionButton label={ref.trim() ? "Сохранить" : "Чек выдан, без ссылки"} busy="Сохраняю…" done="Сохранено" tone="quiet" onRun={save(false)} />
      </div>
    </div>
  );
}

const REVIEW_STATUS: Record<string, string> = {
  approved: "на сайте",
  hidden: "не публикуется",
  pending: "ждёт вашего решения",
};

/** Отзыв клиента по акту — оценка, текст и где он виден. */
function ReviewLine({ review }: { review: NonNullable<WorkAct["review"]> }) {
  const where = !review.text
    ? null
    : review.publish_consent
      ? REVIEW_STATUS[review.status] || review.status
      : "только для вас";
  return (
    <p className="mt-2 text-lw-sm text-lw-ink">
      Отзыв: {review.score ? "⭐".repeat(review.score) : "без оценки"}
      {review.text ? <span className="text-lw-muted"> «{review.text}»</span> : null}
      {where ? <span className="text-lw-muted"> · {where}</span> : null}
    </p>
  );
}

function ActRow({
  act,
  initData,
  onChanged,
}: {
  act: WorkAct;
  initData: string;
  onChanged: () => void;
}) {
  return (
    <div className="rounded-xl bg-lw-cell p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="text-lw-base font-medium text-lw-ink">№ {act.act_number}</span>
        <span className="tabular-nums text-lw-base font-medium text-lw-ink">
          {formatRub(act.amount_minor)}
        </span>
      </div>
      <p className="mt-1 whitespace-pre-wrap text-lw-sm text-lw-ink">{act.description_text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-lw-sm">
        <Pill tone={actStatusTone(act.status)}>{label(WORK_ACT_STATUS, act.status)}</Pill>
        <span className="text-lw-muted">{shortDate(act.created_at)}</span>
        {act.paid_note ? <span className="text-lw-muted">· {act.paid_note}</span> : null}
      </div>

      {act.status === "draft" ? (
        <div className="mt-2">
          <ActionButton
            label="Отправить клиенту"
            busy="Отправляю…"
            done="Отправлен"
            tone="quiet"
            onRun={async () => {
              await lawyerAction(`/api/lawyer/acts/${act.act_id}/send`, initData);
              onChanged();
            }}
          />
        </div>
      ) : null}
      {act.status === "sent" ? (
        <div className="mt-2">
          {act.last_reminded_at &&
          Date.now() - new Date(act.last_reminded_at).getTime() < 24 * 3600 * 1000 ? (
            <p className="text-lw-sm text-lw-muted">Об оплате напомнили {shortDate(act.last_reminded_at)}.</p>
          ) : (
            <ActionButton
              label="Напомнить клиенту об оплате"
              busy="Отправляю…"
              done="Напоминание отправлено"
              tone="quiet"
              onRun={async () => {
                await lawyerAction(`/api/lawyer/acts/${act.act_id}/remind`, initData);
                onChanged();
              }}
            />
          )}
        </div>
      ) : null}
      {act.status === "paid" ? <ReceiptBox act={act} initData={initData} onChanged={onChanged} /> : null}
      {act.review ? <ReviewLine review={act.review} /> : null}
      {act.status === "sent" || act.status === "claimed_paid" ? (
        <div className="mt-2">
          <ActionButton
            label="Отметить оплаченным"
            busy="Отмечаю…"
            done="Оплачен"
            tone="quiet"
            onRun={async () => {
              await lawyerAction(`/api/lawyer/acts/${act.act_id}/paid`, initData, {});
              onChanged();
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

const draftKey = (agreementId: string) => `lawyer.act.${agreementId}`;

function NewActForm({
  agreementId,
  initData,
  defaults,
  onCreated,
}: {
  agreementId: string;
  initData: string;
  defaults: { description: string; amountMinor: number | null };
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          const draft = readDraft<{ description: string; amount: string }>(draftKey(agreementId), {
            description: defaults.description,
            amount: defaults.amountMinor === null ? "" : String(defaults.amountMinor / 100),
          });
          setDescription(draft.description);
          setAmount(draft.amount);
          setOpen(true);
        }}
        className="lw-btn-quiet mt-3 inline-flex"
      >
        Выставить акт
      </button>
    );
  }

  const update = (nextDescription: string, nextAmount: string) => {
    setDescription(nextDescription);
    setAmount(nextAmount);
    writeDraft(draftKey(agreementId), { description: nextDescription, amount: nextAmount });
  };

  return (
    <form
      className="lw-card mt-3 space-y-3 p-4"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await lawyerAction(`/api/lawyer/agreements/${agreementId}/acts`, initData, {
            description_text: description,
            amount,
          });
          dropDraft(draftKey(agreementId));
          setOpen(false);
          setDescription("");
          setAmount("");
          onCreated();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Не удалось составить акт");
        } finally {
          setBusy(false);
        }
      }}
    >
      <p className="text-lw-base font-medium text-lw-ink">Новый акт</p>
      <label className="block">
        <span className="text-lw-sm text-lw-muted">Что сделано</span>
        <textarea
          value={description}
          onChange={(event) => update(event.target.value, amount)}
          rows={4}
          placeholder="Подготовлено и подано заявление, представительство на заседании…"
          className="lw-input mt-1"
        />
      </label>
      <label className="block">
        <span className="text-lw-sm text-lw-muted">Сумма к оплате, ₽</span>
        <input
          inputMode="decimal"
          value={amount}
          onChange={(event) => update(description, event.target.value)}
          placeholder="10 000"
          className="lw-input mt-1"
        />
      </label>
      {error ? <p className="text-lw-sm text-lw-danger">{error}</p> : null}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="lw-btn">
          {busy ? "Составляю…" : "Составить"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="lw-btn-quiet"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}

export default function WorkActBox({
  agreement,
  initData,
  onChanged,
}: {
  agreement: AgreementCard;
  initData: string;
  onChanged: () => void;
}) {
  if (agreement.status !== "signed") return null;

  return (
    <div className="mt-3 border-t border-lw-border pt-3">
      <p className="mb-2 text-lw-sm uppercase tracking-wide text-lw-muted">
        Акты · {agreement.acts.length}
      </p>
      {agreement.acts.length > 0 ? (
        <div className="space-y-2">
          {agreement.acts.map((act) => (
            <ActRow key={act.act_id} act={act} initData={initData} onChanged={onChanged} />
          ))}
        </div>
      ) : null}
      <NewActForm
        agreementId={agreement.agreement_id}
        initData={initData}
        defaults={{
          description: agreement.scope_text || agreement.subject || "",
          amountMinor: agreement.amount_minor,
        }}
        onCreated={onChanged}
      />
    </div>
  );
}
