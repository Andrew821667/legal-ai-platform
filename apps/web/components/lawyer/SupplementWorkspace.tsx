"use client";

import { useCallback, useEffect, useState } from "react";

import { Agreement } from "./ClientCardView";
import SupplementForm from "./SupplementForm";
import { Card, Row } from "./ui";
import { AGREEMENT_STATUS, label, shortDate } from "./labels";
import { LawyerFetchError, lawyerFetch, useTelegramInitData } from "./useTelegram";
import type { AgreementCard, ClientCard } from "./types";
import { formatRub } from "@/lib/money";

/**
 * Допсоглашение — отдельной вкладкой.
 *
 * В карточке клиента форма, отправка и переписка по допсоглашению теснили
 * договор и акты: приходилось листать туда-обратно. Здесь только это дело:
 * договор, к которому соглашение, форма и сами допсоглашения со статусом,
 * отправкой и вопросами клиента. Карточка во вкладке, откуда пришли,
 * обновится сама, когда к ней вернуться.
 *
 * Адрес: /lawyer/supplement?client=<lead_id>&agreement=<agreement_id>.
 */

const OPEN = ["draft", "sent", "viewed"];

function readParams(): { leadId: string; agreementId: string } {
  const params = new URLSearchParams(window.location.search);
  return { leadId: params.get("client") || "", agreementId: params.get("agreement") || "" };
}

export default function SupplementWorkspace() {
  const { initData, ready } = useTelegramInitData();
  const [ids, setIds] = useState<{ leadId: string; agreementId: string } | null>(null);
  const [card, setCard] = useState<ClientCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [formOpen, setFormOpen] = useState<boolean | null>(null);

  useEffect(() => setIds(readParams()), []);

  const load = useCallback(async () => {
    if (!ready || !ids?.leadId) return;
    setError(null);
    try {
      setCard(await lawyerFetch<ClientCard>(`/api/lawyer/clients/${ids.leadId}`, initData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить договор");
      setUnauthorized(err instanceof LawyerFetchError && err.status === 401);
    }
  }, [ready, initData, ids]);

  useEffect(() => {
    void load();
  }, [load]);

  const agreement: AgreementCard | null =
    card?.agreements.find((row) => row.agreement_id === ids?.agreementId) || null;
  const supplements = agreement?.supplements || [];
  const live = supplements.filter((row) => row.status !== "superseded");
  const old = supplements.filter((row) => row.status === "superseded");
  const open = supplements.find((row) => OPEN.includes(row.status)) || null;

  // Форма сразу открыта, пока допсоглашений нет: ради неё вкладку и открыли.
  // Когда оно уже есть, на первом месте — его статус, а новое — по кнопке.
  useEffect(() => {
    if (agreement && formOpen === null) setFormOpen(supplements.length === 0);
  }, [agreement, supplements.length, formOpen]);

  useEffect(() => {
    document.title = card ? `Допсоглашение · ${card.name}` : "Допсоглашение";
  }, [card]);

  const back = ids?.leadId ? `/lawyer?client=${encodeURIComponent(ids.leadId)}` : "/lawyer";

  if (ids && (!ids.leadId || !ids.agreementId)) {
    return <Notice text="В адресе нет клиента или договора." back="/lawyer" />;
  }
  if (unauthorized) {
    return <Notice text="Нет входа в рабочее место. Откройте его и войдите, затем вернитесь сюда." back="/lawyer" />;
  }
  if (error) return <Notice text={error} back={back} />;
  if (!card) return <p className="text-lw-base text-lw-muted">Загружаю…</p>;
  if (!agreement) return <Notice text="Договор не найден у этого клиента." back={back} />;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <a href={back} className="text-lw-base text-lw-muted transition-colors hover:text-lw-primary">
        ← Карточка клиента
      </a>

      <Card>
        <p className="lw-eyebrow">Допсоглашение</p>
        <h1 className="mt-1 text-lw-2xl font-extrabold tracking-tight text-lw-ink">{card.name}</h1>
        <div className="mt-3 border-t border-lw-border pt-2">
          <Row label="Договор" value={`№ ${agreement.number}`} />
          <Row label="Предмет" value={agreement.subject} />
          <Row
            label="Статус"
            value={`${label(AGREEMENT_STATUS, agreement.status)}${agreement.signed_at ? ` ${shortDate(agreement.signed_at)}` : ""}`}
          />
          <Row label="Стоимость" value={agreement.price_text} />
          <Row
            label="Сумма к учёту"
            value={agreement.amount_minor === null ? "не указана" : formatRub(agreement.amount_minor)}
          />
          {open && open.amount_minor !== null ? (
            <Row label="После подписи" value={formatRub(open.amount_minor)} />
          ) : null}
        </div>
      </Card>

      {agreement.status !== "signed" ? (
        <Card>
          <p className="text-lw-base text-lw-ink">
            Договор ещё не подписан — его условия меняются новой редакцией в карточке клиента.
          </p>
        </Card>
      ) : formOpen ? (
        <SupplementForm
          agreementId={agreement.agreement_id}
          currentMinor={agreement.amount_minor}
          replacesOpen={open !== null}
          initData={initData}
          onClose={() => setFormOpen(false)}
          onCreated={() => {
            setFormOpen(false);
            void load();
          }}
        />
      ) : (
        <button type="button" onClick={() => setFormOpen(true)} className="lw-btn-quiet w-full">
          {open ? "Составить заново (заменит неподписанное)" : "Составить новое допсоглашение"}
        </button>
      )}

      {live.length > 0 ? (
        <section className="space-y-2">
          <p className="lw-eyebrow">Допсоглашения · {live.length}</p>
          {live.map((row) => (
            <Agreement key={row.agreement_id} item={row} initData={initData} onChanged={() => void load()} supplement />
          ))}
        </section>
      ) : null}

      {old.length > 0 ? (
        <details className="lw-card p-3">
          <summary className="cursor-pointer text-lw-sm text-lw-muted">Прежние редакции ({old.length})</summary>
          {old.map((row) => (
            <Agreement key={row.agreement_id} item={row} initData={initData} onChanged={() => void load()} supplement />
          ))}
        </details>
      ) : null}
    </div>
  );
}

function Notice({ text, back }: { text: string; back: string }) {
  return (
    <div className="mx-auto max-w-2xl space-y-3">
      <Card>
        <p className="text-lw-base text-lw-ink">{text}</p>
      </Card>
      <a href={back} className="text-lw-base text-lw-primary underline-offset-2 hover:underline">
        ← В рабочее место
      </a>
    </div>
  );
}
