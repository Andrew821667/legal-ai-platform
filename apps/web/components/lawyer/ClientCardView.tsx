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
        className="text-lw-base text-lw-muted transition-colors hover:text-lw-primary lg:hidden"
      >
        ← К списку
      </button>

      <Card>
        {/* Имя крупное — пилюли под ним, а не рядом: на телефоне им тесно. */}
        <h1 className="text-lw-2xl font-extrabold tracking-tight text-lw-ink">{card.name}</h1>
        <p className="mt-0.5 text-lw-base text-lw-muted">
          {card.contact || "контакт не указан"}
          {card.company ? ` · ${card.company}` : ""}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Pill tone={card.stage === "Договор подписан" ? "ok" : "mute"}>{card.stage}</Pill>
          {conflictAlert ? (
            <Pill tone={conflictTone(conflictAlert)}>{label(CONFLICT, conflictAlert)}</Pill>
          ) : null}
        </div>

        <Progress stage={card.stage} />

        {/* Самый юридически значимый статус на карточке — акцентным блоком,
            а не «проваленным» полем: от него зависит, можно ли принимать документы. */}
        <div className={`mt-4 rounded-2xl p-4 ${card.nda ? "bg-lw-success-soft" : "bg-lw-warning-soft"}`}>
          {card.nda ? (
            <>
              <p className="text-lw-base font-semibold text-lw-success">
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
            <p className="text-lw-base font-semibold text-lw-warning">
              NDA не подписан — документы принимаются с пометкой
            </p>
          )}
        </div>
      </Card>

      {loading ? <p className="text-lw-base text-lw-muted">Обновляю…</p> : null}

      <section>
        <SectionTitle count={card.agreements.length}>Договоры</SectionTitle>
        {card.agreements.length === 0 ? (
          <Card>
            <p className="text-lw-sm text-lw-muted">Договоров пока нет.</p>
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
              <details className="lw-card p-3">
                <summary className="cursor-pointer text-lw-sm text-lw-muted">
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
            <p className="text-lw-sm text-lw-muted">Обращений нет.</p>
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
      <p className="text-lw-lg font-bold text-lw-ink">{item.subject}</p>
      <p className="mt-0.5 text-lw-sm text-lw-muted">
        № {item.number}
        {item.revision > 1 ? ` · редакция ${item.revision}` : ""}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Pill tone={statusTone(item.status)}>{label(AGREEMENT_STATUS, item.status)}</Pill>
        {unanswered ? <Pill tone="alert">Ждёт ответа</Pill> : null}
      </div>

      <div className="mt-3 border-t border-lw-border pt-2">
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

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 border-t border-lw-border pt-2 text-lw-sm text-lw-muted">
        <span>составлен {shortDate(item.created_at)}</span>
        {item.sent_at ? <span>отправлен {shortDate(item.sent_at)}</span> : null}
        {item.viewed_at ? <span>просмотрен {shortDate(item.viewed_at)}</span> : null}
        {item.signed_at ? (
          <span className="text-lw-success">подписан {shortDate(item.signed_at)}</span>
        ) : null}
        {item.declined_at ? (
          <span className="text-lw-danger">
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
        <div className="mt-3 border-t border-lw-border pt-3">
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
        <div className="mt-3 border-t border-lw-border pt-3">
          <p className="mb-2 text-lw-sm uppercase tracking-wide text-lw-muted">Переписка</p>
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
                    className={`max-w-[85%] rounded-xl p-3 text-lw-base leading-relaxed ${
                      mine ? "bg-lw-primary-soft text-lw-ink" : "bg-lw-cell text-lw-ink"
                    }`}
                  >
                    <p className="mb-1 text-lw-sm text-lw-muted">
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
      <p className="text-lw-lg font-bold text-lw-ink">{label(AREA, item.legal_area)}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Pill>{label(INTAKE_STATUS, item.status)}</Pill>
        <Pill tone={conflictTone(item.conflict_status)}>{label(CONFLICT, item.conflict_status)}</Pill>
      </div>

      <div className="mt-1 flex flex-wrap gap-x-3 text-lw-sm text-lw-muted">
        <span>{shortDate(item.created_at)}</span>
        <span>{label(URGENCY, item.urgency)}</span>
        {item.deadline_at ? <span>срок до {shortDay(item.deadline_at)}</span> : null}
        {item.region ? <span>{item.region}</span> : null}
      </div>

      {item.outreach_blocked_reason ? (
        <p className="mt-2 text-lw-sm text-lw-warning">
          Связаться не удалось: {label(OUTREACH_REASON, item.outreach_blocked_reason)}
        </p>
      ) : null}

      {conflictBlocks ? (
        <div className={`mt-3 rounded-xl p-3 ${severe ? "bg-lw-danger-soft" : "bg-lw-warning-soft"}`}>
          <p className={`text-lw-sm ${severe ? "text-lw-danger" : "text-lw-warning"}`}>
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

      <p className="mt-3 whitespace-pre-wrap text-lw-base leading-relaxed text-lw-ink">
        {item.description}
      </p>

      {item.clarifications.length > 0 ? (
        <div className="mt-3 border-t border-lw-border pt-3">
          <p className="mb-2 text-lw-sm uppercase tracking-wide text-lw-muted">
            Что уточнили · {item.clarifications.length}
          </p>
          <dl className="space-y-2">
            {item.clarifications.map((row, index) => (
              <div key={index}>
                <dt className="text-lw-sm text-lw-muted">{row.question}</dt>
                <dd className="text-lw-base leading-relaxed text-lw-ink">{row.answer}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {item.documents.length > 0 ? (
        <div className="mt-3 border-t border-lw-border pt-3">
          <p className="mb-2 text-lw-sm uppercase tracking-wide text-lw-muted">
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
        <p className="mt-3 rounded-xl bg-lw-cell p-3 text-lw-sm text-lw-ink">{blocker}</p>
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
