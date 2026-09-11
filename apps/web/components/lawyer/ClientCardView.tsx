"use client";

import ActionButton from "./ActionButton";
import AgreementForm from "./AgreementForm";
import AmountBox from "./AmountBox";
import DeadlineBox from "./DeadlineBox";
import DocumentRow from "./DocumentRow";
import DocumentText from "./DocumentText";
import HistoryList from "./HistoryList";
import NoteBox from "./NoteBox";
import ReplyBox from "./ReplyBox";
import { Card, Pill, Progress, Row, SectionTitle } from "./ui";
import { lawyerAction } from "./useTelegram";
import {
  AGREEMENT_STATUS,
  AREA,
  CONFLICT,
  CONFLICT_EXPLAINED,
  INTAKE_STATUS,
  OUTREACH_REASON,
  URGENCY,
  label,
  shortDate,
  shortDay,
} from "./labels";
import type { AgreementCard, ClientCard, IntakeCard } from "./types";

/**
 * Карточку открывают, чтобы вспомнить всё о деле перед разговором.
 *
 * Поэтому здесь ничего не спрятано за раскрывашками: ответы клиента, документы
 * и переписка по договору видны сразу. Прежняя версия прятала их, и статус
 * приходилось искать.
 */

function statusTone(status: string) {
  if (status === "signed") return "ok" as const;
  if (status === "declined" || status === "expired" || status === "cancelled") return "alert" as const;
  if (status === "draft") return "warn" as const;
  if (status === "superseded") return "mute" as const;
  return "mute" as const;
}

function conflictTone(status: string) {
  if (status === "clear") return "ok" as const;
  if (status === "conflict" || status === "potential") return "alert" as const;
  return "warn" as const;
}

/**
 * Худшая проверка конфликта среди обращений клиента.
 *
 * Поднимаем её в шапку карточки: это не справочное поле, а условие работы —
 * ядро отказывается создавать договор, пока проверка не пройдена, — и цена
 * пропущенного конфликта репутационная, а не операционная.
 */
const CONFLICT_RANK: Record<string, number> = { clear: 0, unchecked: 1, potential: 2, conflict: 3 };

function worstConflict(intakes: IntakeCard[]): string | null {
  let worst: string | null = null;
  for (const item of intakes) {
    if ((CONFLICT_RANK[item.conflict_status] ?? 0) > (CONFLICT_RANK[worst ?? "clear"] ?? 0)) {
      worst = item.conflict_status;
    }
  }
  return worst;
}

export default function ClientCardView({
  card,
  onBack,
  onChanged,
  loading,
  initData,
}: {
  card: ClientCard;
  onBack: () => void;
  onChanged: () => void;
  loading: boolean;
  initData: string;
}) {
  const active = card.agreements.filter((a) => a.status !== "superseded");
  const history = card.agreements.filter((a) => a.status === "superseded");
  const conflictAlert = worstConflict(card.intakes);

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="text-base text-slate-400 transition-colors hover:text-slate-200 lg:hidden"
      >
        ← К списку
      </button>

      <Card>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-white">{card.name}</h1>
            <p className="mt-0.5 text-base text-slate-400">
              {card.contact || "контакт не указан"}
              {card.company ? ` · ${card.company}` : ""}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <Pill tone={card.stage === "Договор подписан" ? "ok" : "mute"}>{card.stage}</Pill>
            {conflictAlert ? (
              <Pill tone={conflictTone(conflictAlert)}>{label(CONFLICT, conflictAlert)}</Pill>
            ) : null}
          </div>
        </div>

        <Progress stage={card.stage} />

        <div className="mt-4 rounded-xl bg-slate-950/60 p-3">
          {card.nda ? (
            <>
              <p className="text-sm font-medium text-emerald-300">
                Соглашение о конфиденциальности подписано {shortDate(card.nda.signed_at)}
              </p>
              <Row label="Подписант" value={card.nda.signer_full_name} />
              <Row label="Контакт" value={card.nda.signer_contact} />
              <Row label="Организация" value={card.nda.signer_org} />
              <DocumentText
                url={`/api/lawyer/nda/${card.nda.nda_id}/document`}
                title="Точный текст, который подписал клиент"
                initData={initData}
              />
            </>
          ) : (
            <p className="text-sm text-amber-300">
              NDA не подписан — документы принимаются с пометкой
            </p>
          )}
        </div>
      </Card>

      {loading ? <p className="text-base text-slate-400">Обновляю…</p> : null}

      <section>
        <SectionTitle count={card.agreements.length}>Договоры</SectionTitle>
        {card.agreements.length === 0 ? (
          <Card>
            <p className="text-sm text-slate-400">Договоров пока нет.</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {active.map((item) => (
              <Agreement
                key={item.agreement_id}
                item={item}
                initData={initData}
                onChanged={onChanged}
              />
            ))}
            {history.length > 0 ? (
              <details className="rounded-2xl border border-slate-800/60 bg-slate-900/30 p-3">
                <summary className="cursor-pointer text-sm text-slate-400">
                  Прежние редакции ({history.length})
                </summary>
                <div className="mt-2 space-y-2">
                  {history.map((item) => (
                    <Agreement
                      key={item.agreement_id}
                      item={item}
                      initData={initData}
                      onChanged={onChanged}
                    />
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        )}
      </section>

      <section>
        <SectionTitle count={card.intakes.length}>Обращения</SectionTitle>
        {card.intakes.length === 0 ? (
          <Card>
            <p className="text-sm text-slate-400">Обращений нет.</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {card.intakes.map((item) => (
              <Intake
                key={item.intake_id}
                item={item}
                initData={initData}
                onChanged={onChanged}
                agreements={card.agreements.filter((a) => a.intake_id === item.intake_id)}
                ndaSigned={Boolean(card.nda)}
                hasDialog={card.telegram_user_id !== null}
              />
            ))}
          </div>
        )}
      </section>

      <HistoryList leadId={card.lead_id} initData={initData} />
    </div>
  );
}

function Agreement({
  item,
  initData,
  onChanged,
}: {
  item: AgreementCard;
  initData: string;
  onChanged: () => void;
}) {
  const unanswered =
    item.messages.length > 0 && item.messages[item.messages.length - 1].role === "client";
  const client = item.client_snapshot || {};
  const clientName = typeof client.full_name === "string" ? client.full_name : null;
  const clientOrg = typeof client.org === "string" ? client.org : null;

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-base font-medium text-white">{item.subject}</p>
          <p className="mt-0.5 text-sm text-slate-400">
            № {item.number}
            {item.revision > 1 ? ` · редакция ${item.revision}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Pill tone={statusTone(item.status)}>{label(AGREEMENT_STATUS, item.status)}</Pill>
          {unanswered ? <Pill tone="alert">Ждёт ответа</Pill> : null}
        </div>
      </div>

      <div className="mt-3 border-t border-slate-800/60 pt-2">
        <Row label="Стоимость" value={item.price_text} />
        {item.status === "superseded" ? null : (
          <AmountBox
            agreementId={item.agreement_id}
            amountMinor={item.amount_minor}
            initData={initData}
            onChanged={onChanged}
          />
        )}
        <Row label="Оплата" value={item.payment_terms} />
        <Row label="Что входит" value={item.scope_text} />
        <Row label="Не входит" value={item.exclusions_text} />
        <Row label="Сроки" value={item.schedule_text} />
        <Row label="Подписант" value={clientName} />
        <Row label="Организация" value={clientOrg} />
        <Row label="Должность" value={item.signer_position} />
        <Row label="Основание" value={item.authority_basis} />
      </div>

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 border-t border-slate-800/60 pt-2 text-sm text-slate-400">
        <span>составлен {shortDate(item.created_at)}</span>
        {item.sent_at ? <span>отправлен {shortDate(item.sent_at)}</span> : null}
        {item.viewed_at ? <span>просмотрен {shortDate(item.viewed_at)}</span> : null}
        {item.signed_at ? (
          <span className="text-emerald-400">подписан {shortDate(item.signed_at)}</span>
        ) : null}
        {item.declined_at ? (
          <span className="text-rose-400">
            отклонён {shortDate(item.declined_at)}
            {item.decline_reason ? ` — «${item.decline_reason}»` : ""}
          </span>
        ) : null}
        {item.expires_at ? <span>действует до {shortDate(item.expires_at)}</span> : null}
      </div>

      {item.status !== "draft" ? (
        <DocumentText
          url={`/api/lawyer/agreements/${item.agreement_id}/document`}
          title={
            item.status === "signed"
              ? "Точный текст, который подписал клиент"
              : "Точный текст, который получил клиент"
          }
          initData={initData}
        />
      ) : null}

      {item.status === "draft" ? (
        <div className="mt-3 border-t border-slate-800/60 pt-3">
          <ActionButton
            label="Отправить клиенту"
            done="Отправлено. Клиент получил проект договора."
            onRun={async () => {
              await lawyerAction(`/api/lawyer/agreements/${item.agreement_id}/deliver`, initData);
              onChanged();
            }}
          />
        </div>
      ) : null}

      {item.messages.length > 0 ? (
        <div className="mt-3 border-t border-slate-800/60 pt-3">
          <p className="mb-2 text-sm uppercase tracking-wide text-slate-400">Переписка</p>
          {/* Раздел живёт внутри Telegram, где «своё справа, чужое слева» —
              рефлекс. Раньше оба голоса шли одинаковыми блоками во всю ширину,
              и при беглом скролле приходилось читать подпись, чтобы понять,
              кто говорит. */}
          <div className="space-y-2">
            {item.messages.map((message, index) => {
              const mine = message.role !== "client";
              return (
                <div key={index} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-xl p-3 text-base leading-relaxed ${
                      mine ? "bg-amber-500/10 text-amber-100" : "bg-slate-800/70 text-slate-200"
                    }`}
                  >
                    <p className="mb-1 text-sm text-slate-400">
                      {mine ? "Вы" : "Клиент"} · {shortDate(message.created_at)}
                    </p>
                    {message.text}
                  </div>
                </div>
              );
            })}
          </div>
          {unanswered ? (
            <ReplyBox
              agreementId={item.agreement_id}
              initData={initData}
              onSent={onChanged}
            />
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

function Intake({
  item,
  initData,
  onChanged,
  agreements,
  ndaSigned,
  hasDialog,
}: {
  item: IntakeCard;
  initData: string;
  onChanged: () => void;
  agreements: AgreementCard[];
  ndaSigned: boolean;
  hasDialog: boolean;
}) {
  const conflictBlocks = item.conflict_status !== "clear";
  const severe = item.conflict_status === "conflict";

  // Условия ядра: подписанный договор не переписывают, а остальное оно
  // отвергает с 409 — лучше назвать причину заранее, чем показать кнопку,
  // которая упрётся в отказ.
  const signed = agreements.some((a) => a.status === "signed");
  const openAgreement = agreements.some((a) => a.status !== "superseded" && a.status !== "signed");
  const blocker = conflictBlocks
    ? null // о проверке конфликта рядом уже сказано подробно
    : !ndaSigned
      ? "Договор нельзя составить, пока клиент не подписал соглашение о конфиденциальности."
      : !hasDialog
        ? "У клиента нет диалога в Telegram — отправить договор будет некуда."
        : null;

  const markConflict = async (status: "clear" | "conflict") => {
    await lawyerAction(`/api/lawyer/intakes/${item.intake_id}/conflict`, initData, {
      conflict_status: status,
    });
    onChanged();
  };

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 text-base font-medium text-white">{label(AREA, item.legal_area)}</p>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Pill>{label(INTAKE_STATUS, item.status)}</Pill>
          <Pill tone={conflictTone(item.conflict_status)}>
            {label(CONFLICT, item.conflict_status)}
          </Pill>
        </div>
      </div>

      <div className="mt-1 flex flex-wrap gap-x-3 text-sm text-slate-400">
        <span>{shortDate(item.created_at)}</span>
        <span>{label(URGENCY, item.urgency)}</span>
        {item.deadline_at ? <span>срок до {shortDay(item.deadline_at)}</span> : null}
        {item.region ? <span>{item.region}</span> : null}
      </div>

      {item.outreach_blocked_reason ? (
        <p className="mt-2 text-sm text-amber-300">
          Связаться не удалось: {label(OUTREACH_REASON, item.outreach_blocked_reason)}
        </p>
      ) : null}

      {conflictBlocks ? (
        <div className={`mt-3 rounded-xl p-3 ${severe ? "bg-rose-500/10" : "bg-amber-500/10"}`}>
          <p className={`text-sm ${severe ? "text-rose-200" : "text-amber-200"}`}>
            {CONFLICT_EXPLAINED[item.conflict_status] || label(CONFLICT, item.conflict_status)}
          </p>
          {severe ? null : (
            <div className="mt-3 flex gap-2">
              <div className="flex-1">
                <ActionButton
                  label="Конфликта нет"
                  busy="Отмечаю…"
                  done="Проверка пройдена — договор можно составлять."
                  onRun={() => markConflict("clear")}
                />
              </div>
              <div className="flex-1">
                <ActionButton
                  label="Есть конфликт"
                  tone="quiet"
                  busy="Отмечаю…"
                  done="Отмечен конфликт интересов."
                  onRun={() => markConflict("conflict")}
                />
              </div>
            </div>
          )}
        </div>
      ) : null}

      <p className="mt-3 whitespace-pre-wrap text-base leading-relaxed text-slate-300">
        {item.description}
      </p>

      {item.clarifications.length > 0 ? (
        <div className="mt-3 border-t border-slate-800/60 pt-3">
          <p className="mb-2 text-sm uppercase tracking-wide text-slate-400">
            Что уточнили · {item.clarifications.length}
          </p>
          <dl className="space-y-2">
            {item.clarifications.map((row, index) => (
              <div key={index}>
                <dt className="text-sm text-slate-400">{row.question}</dt>
                <dd className="text-base leading-relaxed text-slate-200">{row.answer}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {item.documents.length > 0 ? (
        <div className="mt-3 border-t border-slate-800/60 pt-3">
          <p className="mb-2 text-sm uppercase tracking-wide text-slate-400">
            Документы · {item.documents.length}
          </p>
          <ul className="space-y-1.5">
            {item.documents.map((doc) => (
              <DocumentRow key={doc.document_id} doc={doc} initData={initData} />
            ))}
          </ul>
        </div>
      ) : null}

      {signed ? null : blocker ? (
        <p className="mt-3 rounded-xl bg-slate-800/60 p-3 text-sm text-slate-300">{blocker}</p>
      ) : conflictBlocks ? null : (
        <AgreementForm
          intakeId={item.intake_id}
          initData={initData}
          again={openAgreement}
          onCreated={onChanged}
        />
      )}

      <DeadlineBox
        intakeId={item.intake_id}
        deadlineAt={item.deadline_at}
        clientWords={item.deadline}
        initData={initData}
        onChanged={onChanged}
      />

      <NoteBox intakeId={item.intake_id} initialNote={item.internal_note} initData={initData} />
    </Card>
  );
}
