"use client";

import { useState } from "react";

import ActionButton from "./ActionButton";
import { footprintText } from "./ArchiveView";
import ConfirmButton from "./ConfirmButton";
import AgreementForm from "./AgreementForm";
import AmountBox from "./AmountBox";
import DeadlineBox from "./DeadlineBox";
import DocumentRow from "./DocumentRow";
import DocumentText from "./DocumentText";
import HistoryList from "./HistoryList";
import IntakeLinks from "./IntakeLinks";
import NoteBox from "./NoteBox";
import ReplyBox from "./ReplyBox";
import RichText from "./RichText";
import SupplementForm from "./SupplementForm";
import WorkActBox from "./WorkActBox";
import { Card, Pill, Progress, Row, SectionTitle } from "./ui";
import { lawyerAction } from "./useTelegram";
import {
  AGREEMENT_STATUS,
  CLIENT_TYPE,
  CONFLICT,
  CONFLICT_EXPLAINED,
  INTAKE_STATUS,
  OUTREACH_REASON,
  PRACTICE,
  SOURCE,
  URGENCY,
  intakeTitle,
  label,
  shortDate,
  shortDay,
} from "./labels";
import type { AgreementCard, ClientCard, IntakeCard } from "./types";
import { clientContacts } from "@/lib/lawyer-contacts";
import { matterStage, WITHOUT_AGREEMENT_STAGE } from "@/lib/lawyer-stage";

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
    // У инженерного обращения непроверенный конфликт — не тревога: проверка
    // там не условие договора. Отмеченный конфликт показываем всегда.
    if (item.practice === "engineering" && item.conflict_status === "unchecked") continue;
    if ((CONFLICT_RANK[item.conflict_status] ?? 0) > (CONFLICT_RANK[worst ?? "clear"] ?? 0)) {
      worst = item.conflict_status;
    }
  }
  return worst;
}

/**
 * Кто перед нами — компания, ИП или человек. Тип живёт в обращении, а не в
 * клиенте; берём из последнего, где он назван. «unknown» не показываем:
 * пилюля «неизвестно» ничего не сообщает.
 */
function knownClientType(intakes: IntakeCard[]): string | null {
  const known = intakes.find((item) => item.client_type in CLIENT_TYPE);
  return known ? known.client_type : null;
}

export default function ClientCardView({
  card,
  onBack,
  onChanged,
  onOpenClient,
  onArchiveChange,
  loading,
  initData,
  insideTelegram,
}: {
  card: ClientCard;
  onBack: () => void;
  onChanged: () => void;
  onOpenClient: (leadId: string) => void;
  /** Клиент убран в архив, возвращён или удалён совсем. */
  onArchiveChange?: (kind: "archived" | "restored" | "purged") => void;
  loading: boolean;
  initData: string;
  insideTelegram: boolean;
}) {
  const active = card.agreements.filter((a) => a.status !== "superseded");
  const history = card.agreements.filter((a) => a.status === "superseded");
  const conflictAlert = worstConflict(card.intakes);
  const clientType = knownClientType(card.intakes);
  const contacts = clientContacts(card);
  // Что пропадёт при удалении — по тому, что уже есть в карточке.
  const mainAgreements = card.agreements.filter((a) => a.status !== "superseded");
  const footprint = {
    intakes: card.intakes.length,
    agreements: mainAgreements.length,
    signed_agreements: mainAgreements.filter((a) => a.status === "signed").length,
    acts: card.agreements.reduce((sum, a) => sum + a.acts.length, 0),
    nda_signed: Boolean(card.nda),
  };
  // Шкала «обращение → NDA → договор → подписан» у такого клиента звала бы
  // к договору, который юрист сознательно решил не заключать.
  const withoutAgreement = card.stage === WITHOUT_AGREEMENT_STAGE;

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
        {card.company ? <p className="mt-0.5 text-lw-base text-lw-muted">{card.company}</p> : null}
        {/* Контакты — ссылками: карточку открывают перед разговором, и по
            контакту отсюда нужно сразу написать или позвонить. */}
        <p className="mt-0.5 flex flex-wrap gap-x-3 text-lw-base text-lw-muted">
          {contacts.length === 0 ? <span>контакт не указан</span> : null}
          {contacts.map((item) =>
            item.href ? (
              <a key={item.value} href={item.href} className="text-lw-primary underline-offset-2 hover:underline">
                {item.value}
              </a>
            ) : (
              <span key={item.value}>{item.value}</span>
            ),
          )}
        </p>
        <p className="mt-1 text-lw-sm text-lw-muted">
          с {shortDate(card.created_at)}
          {card.source ? ` · ${label(SOURCE, card.source)}` : ""}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {card.is_test ? <Pill tone="alert">Тест · ваш аккаунт</Pill> : null}
          <Pill tone={card.stage === "Договор подписан" || withoutAgreement ? "ok" : "mute"}>{card.stage}</Pill>
          {clientType ? <Pill>{label(CLIENT_TYPE, clientType)}</Pill> : null}
          {conflictAlert ? (
            <Pill tone={conflictTone(conflictAlert)}>{label(CONFLICT, conflictAlert)}</Pill>
          ) : null}
        </div>

        {/* Шкала хода — одна сделка. У клиента с несколькими обращениями она
            стоит у каждого из них, а не в шапке: там показала бы только одно. */}
        {card.intakes.length > 1 || withoutAgreement ? null : <Progress stage={card.stage} />}

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
              <Row label="Документ" value={card.nda.identity_document_provided ? "реквизиты предоставлены" : null} />
              <Row
                label="Согласие на обработку ПД"
                value={card.nda.pdn_consent_at ? `дано ${shortDate(card.nda.pdn_consent_at)}` : null}
              />
              {card.nda.pdn_consent_id ? (
                <DocumentText
                  url={`/api/lawyer/nda-consents/${card.nda.pdn_consent_id}/document`}
                  title="Отдельное согласие на обработку ПД"
                  initData={initData}
                />
              ) : null}
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

      {card.archived_at ? (
        <div className="rounded-2xl bg-lw-warning-soft p-4">
          <p className="text-lw-base font-semibold text-lw-warning">
            Клиент в архиве с {shortDate(card.archived_at)}
          </p>
          <p className="mt-1 text-lw-sm text-lw-ink">
            Его нет в списке, задачах и деньгах. Бот не пишет ему первым; если клиент сам придёт
            с новым вопросом — вернётся в список.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <ConfirmButton
              label="Восстановить"
              explain="Клиент вернётся в список со всеми обращениями и договорами."
              confirmLabel="Вернуть в список"
              busy="Возвращаю…"
              onConfirm={async () => {
                await lawyerAction(`/api/lawyer/clients/${card.lead_id}/restore`, initData);
                onArchiveChange?.("restored");
              }}
            />
            <ConfirmButton
              label="Удалить навсегда"
              danger
              explain={
                <>
                  <p className="font-semibold">Удалить «{card.name}» без возможности восстановления?</p>
                  <p className="mt-1">Пропадёт: {footprintText(footprint)}, переписка и история.</p>
                  {footprint.signed_agreements || footprint.acts || footprint.nda_signed ? (
                    <p className="mt-1 text-lw-danger">
                      Среди них подписанные документы — после удаления их не восстановить.
                    </p>
                  ) : null}
                </>
              }
              confirmLabel="Удалить навсегда"
              busy="Удаляю…"
              onConfirm={async () => {
                await lawyerAction(`/api/lawyer/clients/${card.lead_id}`, initData, undefined, "DELETE");
                onArchiveChange?.("purged");
              }}
            />
          </div>
        </div>
      ) : null}

      {loading ? <p className="text-lw-base text-lw-muted">Обновляю…</p> : null}

      {withoutAgreement && card.agreements.length === 0 ? null : (
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
                leadId={card.lead_id}
                insideTelegram={insideTelegram}
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
      )}

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
                ownProgress={card.intakes.length > 1}
                insideTelegram={insideTelegram}
                currentLeadId={card.lead_id}
                onOpenClient={onOpenClient}
              />
            ))}
          </div>
        )}
      </section>

      <HistoryList leadId={card.lead_id} initData={initData} />

      {card.archived_at ? null : (
        <ConfirmButton
          label="Удалить клиента"
          explain={
            <p>
              Клиент уйдёт в архив: пропадёт из списка, задач и денег, но ничего не удалится.
              Из архива его можно восстановить или удалить совсем.
            </p>
          }
          confirmLabel="Убрать в архив"
          busy="Убираю…"
          danger
          onConfirm={async () => {
            await lawyerAction(`/api/lawyer/clients/${card.lead_id}/archive`, initData);
            onArchiveChange?.("archived");
          }}
        />
      )}
    </div>
  );
}

const OPEN_STATUSES = ["draft", "sent", "viewed"];

/** Отдельная вкладка допсоглашения: составить, отправить, вести переписку. */
export function supplementPageHref(leadId: string, agreementId: string): string {
  return `/lawyer/supplement?client=${encodeURIComponent(leadId)}&agreement=${encodeURIComponent(agreementId)}`;
}

export function Agreement({
  item,
  initData,
  onChanged,
  supplement = false,
  leadId,
  insideTelegram = false,
}: {
  item: AgreementCard;
  initData: string;
  onChanged: () => void;
  /** Допсоглашение внутри карточки своего договора: без суммы к учёту и актов. */
  supplement?: boolean;
  /** Есть — «допсоглашение» открывается отдельной вкладкой (вне Telegram). */
  leadId?: string;
  insideTelegram?: boolean;
}) {
  const unanswered =
    item.messages.length > 0 && item.messages[item.messages.length - 1].role === "client";
  const client = item.client_snapshot || {};
  const clientName = typeof client.full_name === "string" ? client.full_name : null;
  const clientOrg = typeof client.org === "string" ? client.org : null;

  const supplements = item.supplements || [];
  const liveSupplements = supplements.filter((row) => row.status !== "superseded");
  const oldSupplements = supplements.filter((row) => row.status === "superseded");
  // Новые первыми — первое открытое и есть то, что сейчас у клиента.
  const openSupplement = supplements.find((row) => OPEN_STATUSES.includes(row.status)) || null;
  const [supplementOpen, setSupplementOpen] = useState(false);

  const body = (
    <>
      <p className={supplement ? "text-lw-base font-semibold text-lw-ink" : "text-lw-lg font-bold text-lw-ink"}>
        {supplement ? item.subject.split(" к договору")[0] : item.subject}
      </p>
      <p className="mt-0.5 text-lw-sm text-lw-muted">
        № {item.number}
        {item.revision > 1 ? ` · редакция ${item.revision}` : ""}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Pill tone={statusTone(item.status)}>{label(AGREEMENT_STATUS, item.status)}</Pill>
        {unanswered ? <Pill tone="alert">Ждёт ответа</Pill> : null}
      </div>

      {supplement ? (
        <div className="mt-3 border-t border-lw-border pt-2">
          <Row label="Работы" value={item.scope_text} />
          <Row label="Сроки" value={item.schedule_text || "как в договоре"} />
          <Row label="Новая стоимость" value={item.price_text} />
          <Row label="Оплата" value={item.payment_terms || "как в договоре"} />
        </div>
      ) : (
        <div className="mt-3 border-t border-lw-border pt-2">
          <Row label="Стоимость" value={item.price_text} />
          {item.status === "superseded" ? null : (
            <AmountBox
              agreementId={item.agreement_id}
              amountMinor={item.amount_minor}
              pendingMinor={openSupplement?.amount_minor ?? null}
              onSupplement={item.status === "signed" ? () => setSupplementOpen(true) : undefined}
              // В браузере — отдельной вкладкой: форма, отправка и переписка
              // не теснят карточку. В мини-аппе Telegram новое окно уводит из
              // приложения, поэтому там форма остаётся на месте.
              supplementHref={
                item.status === "signed" && leadId && !insideTelegram
                  ? supplementPageHref(leadId, item.agreement_id)
                  : undefined
              }
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
      )}

      {supplementOpen ? (
        <SupplementForm
          agreementId={item.agreement_id}
          currentMinor={item.amount_minor}
          replacesOpen={openSupplement !== null}
          initData={initData}
          onClose={() => setSupplementOpen(false)}
          onCreated={() => {
            setSupplementOpen(false);
            onChanged();
          }}
        />
      ) : null}

      {liveSupplements.length > 0 ? (
        <div className="mt-3 border-t border-lw-border pt-3">
          <p className="text-lw-sm uppercase tracking-wide text-lw-muted">
            Допсоглашения · {liveSupplements.length}
          </p>
          {liveSupplements.map((row) => (
            <Agreement key={row.agreement_id} item={row} initData={initData} onChanged={onChanged} supplement />
          ))}
          {oldSupplements.length > 0 ? (
            <details className="mt-2">
              <summary className="cursor-pointer text-lw-sm text-lw-muted">
                Прежние редакции ({oldSupplements.length})
              </summary>
              {oldSupplements.map((row) => (
                <Agreement key={row.agreement_id} item={row} initData={initData} onChanged={onChanged} supplement />
              ))}
            </details>
          ) : null}
        </div>
      ) : null}

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
            done={
              supplement
                ? "Отправлено. Клиент получил допсоглашение."
                : "Отправлено. Клиент получил проект договора."
            }
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

      {supplement ? null : <WorkActBox agreement={item} initData={initData} onChanged={onChanged} />}
    </>
  );

  return supplement ? <div className="mt-2 rounded-xl bg-lw-cell p-3">{body}</div> : <Card>{body}</Card>;
}

function Intake({
  item,
  initData,
  onChanged,
  agreements,
  ndaSigned,
  hasDialog,
  ownProgress,
  insideTelegram,
  currentLeadId,
  onOpenClient,
}: {
  item: IntakeCard;
  initData: string;
  onChanged: () => void;
  agreements: AgreementCard[];
  ndaSigned: boolean;
  hasDialog: boolean;
  ownProgress: boolean;
  insideTelegram: boolean;
  currentLeadId: string;
  onOpenClient: (leadId: string) => void;
}) {
  // NDA обязателен всем, проверка конфликта блокирует право и гибрид.
  const gated = item.practice !== "engineering";
  const conflictBlocks = gated && item.conflict_status !== "clear";
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

  // Развилка после NDA: договор для дела не нужен — консультация, разовый
  // документ. Те же условия, что проверяет ядро (иначе оно ответит 409):
  // NDA подписан, конфликт проверен, договоров по делу ещё нет, дело живое.
  const closed = item.status === "closed" || item.status === "declined";
  const canWorkWithoutAgreement =
    !item.without_agreement && agreements.length === 0 && ndaSigned && !conflictBlocks && !closed;
  // Ведём без договора и договоров по делу нет — о договоре молчим, кроме
  // одной кнопки: клиент может вернуться с отдельной задачей, где он нужен.
  const withoutAgreement = item.without_agreement && agreements.length === 0;
  const [agreementAnyway, setAgreementAnyway] = useState(false);
  const workWithoutAgreement = async () => {
    await lawyerAction(`/api/lawyer/intakes/${item.intake_id}/without-agreement`, initData);
    onChanged();
  };

  return (
    <Card>
      <p className="text-lw-lg font-bold text-lw-ink">{intakeTitle(item)}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {item.practice !== "legal" ? <Pill tone="mute">{label(PRACTICE, item.practice)}</Pill> : null}
        <Pill>{label(INTAKE_STATUS, item.status)}</Pill>
        {withoutAgreement ? <Pill tone="mute">Без договора</Pill> : null}
        {/* У инженерного обращения проверка конфликта — пометка, а не условие;
            непроверенную не показываем, чтобы не читалась как преграда. */}
        {gated || item.conflict_status !== "unchecked" ? (
          <Pill tone={conflictTone(item.conflict_status)}>{label(CONFLICT, item.conflict_status)}</Pill>
        ) : null}
      </div>

      <div className="mt-1 flex flex-wrap gap-x-3 text-lw-sm text-lw-muted">
        <span>{shortDate(item.created_at)}</span>
        <span>{label(URGENCY, item.urgency)}</span>
        {item.deadline_at ? <span>срок до {shortDay(item.deadline_at)}</span> : null}
        {item.region ? <span>{item.region}</span> : null}
      </div>

      {ownProgress && !withoutAgreement ? <Progress stage={matterStage(agreements, ndaSigned)} /> : null}

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

      <RichText text={item.description} className="mt-3" />

      {item.clarifications.length > 0 ? (
        <div className="mt-3 border-t border-lw-border pt-3">
          <p className="mb-2 text-lw-sm uppercase tracking-wide text-lw-muted">
            Что уточнили · {item.clarifications.length}
          </p>
          <dl className="space-y-2">
            {item.clarifications.map((row, index) => (
              <div key={index}>
                <dt className="text-lw-sm text-lw-muted">{row.question}</dt>
                <dd>
                  <RichText text={row.answer} />
                </dd>
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
              <DocumentRow
                key={doc.document_id}
                doc={doc}
                initData={initData}
                insideTelegram={insideTelegram}
              />
            ))}
          </ul>
        </div>
      ) : null}

      {signed ? null : withoutAgreement && !agreementAnyway ? (
        <button type="button" onClick={() => setAgreementAnyway(true)} className="lw-btn-quiet mt-3 w-full">
          Заключить договор
        </button>
      ) : blocker ? (
        <p className="mt-3 rounded-xl bg-lw-cell p-3 text-lw-sm text-lw-ink">{blocker}</p>
      ) : conflictBlocks ? null : (
        <AgreementForm
          intakeId={item.intake_id}
          initData={initData}
          again={openAgreement}
          startOpen={agreementAnyway}
          onCreated={onChanged}
        />
      )}

      {canWorkWithoutAgreement ? (
        <div className="mt-3 rounded-xl bg-lw-cell p-3">
          <p className="text-lw-sm text-lw-muted">
            Договор для этого дела не нужен — консультация или разовый документ? Обращение
            останется в работе; составить договор позже всё равно можно.
          </p>
          <div className="mt-2">
            <ActionButton
              label="Работать без договора"
              tone="quiet"
              busy="Отмечаю…"
              done="Обращение в работе без договора."
              onRun={workWithoutAgreement}
            />
          </div>
        </div>
      ) : null}

      <DeadlineBox
        intakeId={item.intake_id}
        deadlineAt={item.deadline_at}
        clientWords={item.deadline}
        initData={initData}
        onChanged={onChanged}
      />

      <NoteBox intakeId={item.intake_id} initialNote={item.internal_note} initData={initData} />

      <IntakeLinks
        intakeId={item.intake_id}
        currentLeadId={currentLeadId}
        links={item.links}
        initData={initData}
        onOpen={onOpenClient}
        onChanged={onChanged}
      />
    </Card>
  );
}
