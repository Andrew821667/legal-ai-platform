"use client";

import { useEffect, useRef, useState } from "react";

import { draftToTemplate, templateToDraft, templateWithPackage } from "@/lib/agreement-template";
import type { AgreementTemplate } from "@/lib/agreement-template";
import { packagesForPractice } from "@/lib/starter-offers";
import type { IntakePackage } from "./types";
import { lawyerAction, lawyerFetch } from "./useTelegram";

/**
 * Заготовки условий договора в форме: подставить готовые или сохранить
 * текущие. Раньше предмет, объём, сроки, цену и оплату юрист набирал руками
 * в каждом договоре, хотя для типовых услуг они повторяются.
 *
 * Заготовку можно привязать к пакету услуг сайта. Если клиент заказал пакет,
 * а форма пуста, заготовка под него подставляется сама — договор по
 * пакету собирается без набора.
 */
export default function TemplateBar({
  practice,
  values,
  initData,
  onApply,
  pkg = null,
}: {
  practice: string | null;
  values: Record<string, string>;
  initData: string;
  onApply: (draft: Record<string, string>) => void;
  /** Пакет, выбранный клиентом на сайте. */
  pkg?: IntakePackage | null;
}) {
  const [templates, setTemplates] = useState<AgreementTemplate[]>([]);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [note, setNote] = useState<string | null>(null);
  // Пакет, к которому привязать сохраняемую заготовку. По умолчанию — пакет
  // клиента, если под него заготовки ещё нет: так связь заводится один раз.
  const [packageId, setPackageId] = useState(pkg && !pkg.template_id ? pkg.id : "");
  const autoApplied = useRef(false);
  const packages = packagesForPractice(practice);
  const formEmpty = Object.values(values).every((value) => !(value || "").trim());

  const load = async () => {
    try {
      const query = practice ? `?practice=${encodeURIComponent(practice)}` : "";
      setTemplates(await lawyerFetch<AgreementTemplate[]>(`/api/lawyer/agreement-templates${query}`, initData));
    } catch {
      // Без заготовок форма работает как раньше — ошибка здесь не повод её ломать.
      setTemplates([]);
    }
  };

  useEffect(() => {
    void load();
  }, [practice, initData]);

  const apply = (templateId: string, message?: string) => {
    setSelected(templateId);
    const template = templates.find((t) => t.template_id === templateId);
    if (!template) return;
    onApply(templateToDraft(template));
    setNote(message || `Подставлено из «${template.name}» — поправьте под дело.`);
    void lawyerAction(`/api/lawyer/agreement-templates/${templateId}/used`, initData).catch(() => undefined);
  };

  useEffect(() => {
    // Один раз и только в пустую форму: набранное юристом важнее пакета.
    if (autoApplied.current || !pkg?.template_id || !formEmpty) return;
    const template = templates.find((t) => t.template_id === pkg.template_id);
    if (!template) return;
    autoApplied.current = true;
    const price = pkg.price_text ? ` (на сайте — ${pkg.price_text})` : "";
    apply(
      template.template_id,
      `Клиент заказал пакет «${pkg.title || template.name}»${price} — подставлена заготовка «${template.name}». Проверьте цену и поправьте под дело.`,
    );
  }, [templates, pkg, formEmpty]);

  const linkPackage = async (template: AgreementTemplate, nextPackageId: string) => {
    try {
      await lawyerAction(
        `/api/lawyer/agreement-templates/${template.template_id}`,
        initData,
        templateWithPackage(template, nextPackageId || null),
        "PUT",
      );
      const title = packages.find((p) => p.id === nextPackageId)?.title;
      setNote(title ? `Заготовка «${template.name}» — для пакета «${title}».` : `Заготовка «${template.name}» отвязана от пакета.`);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось привязать к пакету");
    }
  };

  const save = async () => {
    const check = draftToTemplate(values, name, practice, packageId || null);
    if (!check.ok) {
      setNote(check.detail);
      return;
    }
    try {
      await lawyerAction("/api/lawyer/agreement-templates", initData, check.value);
      setSaving(false);
      setName("");
      setNote("Заготовка сохранена.");
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  };

  const current = templates.find((t) => t.template_id === selected) || null;
  // Заготовки под пакет клиента ещё нет — подсказать, как завести её один раз.
  const packageWithoutTemplate = Boolean(pkg && !pkg.template_id && !templates.some((t) => t.package_id === pkg.id));
  const packageSelect = (value: string, onChange: (id: string) => void, emptyLabel: string, wide = false) => (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={`lw-input !py-2 ${wide ? "basis-full" : "!w-auto min-w-0 flex-1"}`}
      aria-label="Пакет на сайте"
    >
      <option value="">{emptyLabel}</option>
      {packages.map((p) => (
        <option key={p.id} value={p.id}>
          {p.title} — {p.price}
        </option>
      ))}
    </select>
  );

  const remove = async () => {
    const template = templates.find((t) => t.template_id === selected);
    if (!template) return;
    try {
      await lawyerAction(`/api/lawyer/agreement-templates/${selected}`, initData, undefined, "DELETE");
      setSelected("");
      setNote(`Заготовка «${template.name}» удалена.`);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось удалить");
    }
  };

  return (
    <div className="rounded-xl bg-lw-cell p-3">
      {packageWithoutTemplate && pkg ? (
        <p className="mb-2 text-lw-sm text-lw-muted">
          Клиент заказал на сайте «{pkg.title || pkg.id}»{pkg.price_text ? ` — ${pkg.price_text}` : ""}. Заготовки под
          этот пакет нет: заполните условия и сохраните их как заготовку с этим пакетом — следующий такой договор
          соберётся сам.
        </p>
      ) : null}
      {templates.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selected}
            onChange={(event) => apply(event.target.value)}
            className="lw-input !w-auto min-w-0 flex-1 !py-2"
            aria-label="Заготовка"
          >
            <option value="">Заготовка…</option>
            {templates.map((t) => (
              <option key={t.template_id} value={t.template_id}>
                {t.name}
              </option>
            ))}
          </select>
          {selected ? (
            <button type="button" onClick={() => void remove()} className="text-lw-sm text-lw-muted underline underline-offset-2 hover:text-lw-danger">
              удалить заготовку
            </button>
          ) : null}
          {current ? (
            <div className="flex w-full flex-wrap items-center gap-2 text-lw-sm text-lw-muted">
              <span>Пакет на сайте:</span>
              {packageSelect(current.package_id || "", (id) => void linkPackage(current, id), "не привязана")}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="text-lw-sm text-lw-muted">Заготовок пока нет — сохраните условия типовой услуги, и они будут здесь.</p>
      )}

      {saving ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Название, например «Проверка договора»"
            className="lw-input min-w-0 flex-1 !py-2"
            maxLength={120}
          />
          {packageSelect(packageId, setPackageId, "Без пакета сайта", true)}
          <button type="button" onClick={() => void save()} className="lw-btn !px-4 !py-2 !text-[15px]">
            Сохранить
          </button>
          <button type="button" onClick={() => setSaving(false)} className="text-lw-sm text-lw-muted hover:text-lw-primary">
            Отмена
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setSaving(true)} className="mt-2 text-lw-sm text-lw-primary underline underline-offset-2">
          Сохранить эти условия как заготовку
        </button>
      )}
      {note ? <p className="mt-2 text-lw-sm text-lw-muted">{note}</p> : null}
    </div>
  );
}
