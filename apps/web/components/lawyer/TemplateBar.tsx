"use client";

import { useEffect, useState } from "react";

import { draftToTemplate, templateToDraft } from "@/lib/agreement-template";
import type { AgreementTemplate } from "@/lib/agreement-template";
import { lawyerAction, lawyerFetch } from "./useTelegram";

/**
 * Заготовки условий договора в форме: подставить готовые или сохранить
 * текущие. Раньше предмет, объём, сроки, цену и оплату юрист набирал руками
 * в каждом договоре, хотя для типовых услуг они повторяются.
 */
export default function TemplateBar({
  practice,
  values,
  initData,
  onApply,
}: {
  practice: string | null;
  values: Record<string, string>;
  initData: string;
  onApply: (draft: Record<string, string>) => void;
}) {
  const [templates, setTemplates] = useState<AgreementTemplate[]>([]);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [note, setNote] = useState<string | null>(null);

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

  const apply = (templateId: string) => {
    setSelected(templateId);
    const template = templates.find((t) => t.template_id === templateId);
    if (!template) return;
    onApply(templateToDraft(template));
    setNote(`Подставлено из «${template.name}» — поправьте под дело.`);
    void lawyerAction(`/api/lawyer/agreement-templates/${templateId}/used`, initData).catch(() => undefined);
  };

  const save = async () => {
    const check = draftToTemplate(values, name, practice);
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
