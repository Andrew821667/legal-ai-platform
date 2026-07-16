export const LEGAL_CLIENT_TYPES = [
  { value: "company", label: "Компания" },
  { value: "entrepreneur", label: "Предприниматель" },
  { value: "individual", label: "Частное лицо" },
  { value: "unknown", label: "Пока не определено" },
] as const;

export const LEGAL_AREAS = [
  { value: "contracts", label: "Договоры и сделки" },
  { value: "disputes", label: "Претензии и споры" },
  { value: "corporate", label: "Корпоративные вопросы" },
  { value: "employment", label: "Трудовые отношения" },
  { value: "tax_compliance", label: "Налоги и комплаенс" },
  { value: "real_estate", label: "Недвижимость и земля" },
  { value: "it_ip_data", label: "IT, интеллектуальная собственность и данные" },
  { value: "family_inheritance", label: "Семейные и наследственные вопросы" },
  { value: "debt_bankruptcy", label: "Долги и банкротство" },
  { value: "other", label: "Другая юридическая задача" },
] as const;

export const LEGAL_URGENCY_LEVELS = [
  { value: "urgent", label: "Срок сегодня или завтра" },
  { value: "high", label: "Срок до трёх дней" },
  { value: "normal", label: "Срок позднее" },
  { value: "no_deadline", label: "Ближайшего срока нет" },
] as const;

export type LegalClientType = (typeof LEGAL_CLIENT_TYPES)[number]["value"];
export type LegalArea = (typeof LEGAL_AREAS)[number]["value"];
export type LegalUrgency = (typeof LEGAL_URGENCY_LEVELS)[number]["value"];
