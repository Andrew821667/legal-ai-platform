"use client";

import { useState } from "react";

import ActionButton from "./ActionButton";
import ReplyBox from "./ReplyBox";
import NoteBox from "./NoteBox";
import { lawyerAction } from "./useTelegram";
import {
  AGREEMENT_STATUS,
  AREA,
  INTAKE_STATUS,
  OUTREACH_REASON,
  URGENCY,
  label,
  shortDate,
} from "./labels";
import type { AgreementCard, ClientCard, IntakeCard } from "./types";

/**
 * Карточку открывают, чтобы за полминуты вспомнить контекст перед разговором.
 * Поэтому сверху — кто это и на чём остановились, а подробности ниже.
 */

export default function ClientCardView({
  card,
  onBack,
  loading,
  initData,
}: {
  card: ClientCard;
  onBack: () => void;
  loading: boolean;
  initData: string;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-3 text-sm text-slate-400 hover:text-slate-200"
      >
        ← Назад
      </button>

      <header className="rounded-xl border border-slate-800 bg-slate-900 p-4">
        <h1 className="text-lg font-semibold text-white">{card.name}</h1>
        <p className="mt-1 text-sm text-slate-400">
          {card.contact || "контакт не указан"}
          {card.company ? ` · ${card.company}` : ""}
        </p>

        <div className="mt-3 rounded-lg bg-slate-800 p-3">
          {card.nda ? (
            <>
              <p className="text-xs font-medium text-emerald-300">
                NDA подписан {shortDate(card.nda.signed_at)}
              </p>
              <p className="mt-0.5 text-xs text-slate-400">
                {card.nda.signer_full_name}
                {card.nda.signer_org ? ` · ${card.nda.signer_org}` : ""}
              </p>
              {card.nda.signer_contact ? (
                <p className="text-xs text-slate-500">{card.nda.signer_contact}</p>
              ) : null}
            </>
          ) : (
            <p className="text-xs text-amber-300">
              NDA не подписан — документы принимаются с пометкой
            </p>
          )}
        </div>
      </header>

      {loading ? <p className="mt-3 text-sm text-slate-400">Обновляю…</p> : null}

      <Section title="Договоры">
        {card.agreements.length === 0 ? (
          <Empty>Договоров пока нет.</Empty>
        ) : (
          card.agreements.map((item) => (
            <Agreement key={item.agreement_id} item={item} initData={initData} />
          ))
        )}
      </Section>

      <Section title="Обращения">
        {card.intakes.length === 0 ? (
          <Empty>Обращений нет.</Empty>
        ) : (
          card.intakes.map((item) => (
            <Intake key={item.intake_id} item={item} initData={initData} />
          ))
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-300">{title}</h2>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs text-slate-500">
      {children}
    </p>
  );
}

function Agreement({ item, initData }: { item: AgreementCard; initData: string }) {
  const unanswered =
    item.messages.length > 0 && item.messages[item.messages.length - 1].role === "client";

  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900 p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-white">{item.subject}</span>
        <span className="shrink-0 text-xs text-slate-400">
          {label(AGREEMENT_STATUS, item.status)}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-400">
        {item.price_text} · № {item.number}
        {item.revision > 1 ? ` · редакция ${item.revision}` : ""}
      </p>
      <p className="mt-1 text-[11px] text-slate-500">
        составлен {shortDate(item.created_at)}
        {item.sent_at ? ` · отправлен ${shortDate(item.sent_at)}` : ""}
        {item.signed_at ? ` · подписан ${shortDate(item.signed_at)}` : ""}
        {item.declined_at ? ` · отклонён ${shortDate(item.declined_at)}` : ""}
      </p>

      {item.status === "draft" ? (
        <div className="mt-2 border-t border-slate-800 pt-2">
          <ActionButton
            label="Отправить клиенту"
            done="Отправлено. Клиент получил проект договора."
            onRun={async () => {
              await lawyerAction(`/api/lawyer/agreements/${item.agreement_id}/deliver`, initData);
            }}
          />
        </div>
      ) : null}

      {item.messages.length > 0 ? (
        <div className="mt-2 space-y-1 border-t border-slate-800 pt-2">
          {unanswered ? (
            <p className="text-[11px] font-medium text-amber-300">Ждёт вашего ответа</p>
          ) : null}
          {item.messages.slice(-3).map((message, index) => (
            <p key={index} className="text-xs text-slate-400">
              <span className={message.role === "client" ? "text-slate-300" : "text-slate-500"}>
                {message.role === "client" ? "Клиент" : "Вы"}:
              </span>{" "}
              {message.text}
            </p>
          ))}
          {unanswered ? <ReplyBox agreementId={item.agreement_id} initData={initData} /> : null}
        </div>
      ) : null}
    </article>
  );
}

function Intake({ item, initData }: { item: IntakeCard; initData: string }) {
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900 p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-white">{label(AREA, item.legal_area)}</span>
        <span className="shrink-0 text-xs text-slate-400">
          {label(INTAKE_STATUS, item.status)}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">
        {shortDate(item.created_at)} · {label(URGENCY, item.urgency)}
        {item.deadline ? ` · срок: ${item.deadline}` : ""}
        {item.region ? ` · ${item.region}` : ""}
      </p>

      {item.outreach_blocked_reason ? (
        <p className="mt-1 text-[11px] text-amber-300">
          Связаться не удалось: {label(OUTREACH_REASON, item.outreach_blocked_reason)}
        </p>
      ) : null}

      <p className="mt-2 whitespace-pre-wrap text-xs text-slate-300">{item.description}</p>

      {item.clarifications.length > 0 ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-slate-400">
            Ответы клиента ({item.clarifications.length})
          </summary>
          <dl className="mt-2 space-y-2">
            {item.clarifications.map((row, index) => (
              <div key={index}>
                <dt className="text-[11px] text-slate-500">{row.question}</dt>
                <dd className="text-xs text-slate-300">{row.answer}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}

      {item.documents.length > 0 ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-slate-400">
            Документы ({item.documents.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {item.documents.map((doc, index) => (
              <li key={index} className="text-xs text-slate-300">
                {doc.file_name || "без имени"}
                {doc.nda_signed_at_upload ? null : (
                  <span className="ml-1 text-[11px] text-amber-400">(без NDA)</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <NoteBox intakeId={item.intake_id} initialNote={item.internal_note} initData={initData} />
    </article>
  );
}
