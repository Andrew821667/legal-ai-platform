export type StarterOfferPractice = "legal" | "engineering";

export type StarterOffer = {
  id: StarterOfferId;
  practice: StarterOfferPractice;
  title: string;
  price: string;
  description: string;
  note: string;
};

export const STARTER_OFFER_EVENT = "starter_offer_selected";

export const starterOffers = {
  legal_consultation: {
    id: "legal_consultation",
    practice: "legal",
    title: "Консультация юриста",
    price: "4 900 ₽",
    description:
      "До 60 минут онлайн и короткий письменный план: что делать дальше, какие документы нужны и какие сроки проверить.",
    note: "После первичного описания подтвердим, что вопрос входит в этот формат.",
  },
  legal_contract_review: {
    id: "legal_contract_review",
    practice: "legal",
    title: "Экспресс-проверка договора",
    price: "от 7 900 ₽",
    description:
      "Проверка одного договора до 15 страниц: существенные условия, риски и перечень предлагаемых правок.",
    note: "Срок и точную цену подтвердим после просмотра объёма и читаемости файла.",
  },
  legal_claim_response: {
    id: "legal_claim_response",
    practice: "legal",
    title: "Претензия или ответ на претензию",
    price: "от 9 900 ₽",
    description:
      "Разберём документы и факты, сформулируем требования или возражения и подготовим документ к отправке.",
    note: "Судебное представительство и дополнительные документы оцениваются отдельно.",
  },
  engineering_diagnostic: {
    id: "engineering_diagnostic",
    practice: "engineering",
    title: "Диагностика автоматизации",
    price: "7 900 ₽",
    description:
      "Разберём один процесс и подготовим технический план: границы задачи, основной пользовательский маршрут, интеграции, риски и следующий этап.",
    note: "Если продолжаем работу над проектом, стоимость диагностики засчитывается в его бюджет.",
  },
  engineering_prototype: {
    id: "engineering_prototype",
    practice: "engineering",
    title: "Прототип Telegram-бота или автоматизации",
    price: "от 39 000 ₽",
    description:
      "Соберём основной рабочий сценарий, чтобы проверить логику решения на реальной задаче до полноценной разработки.",
    note: "Состав прототипа и точную стоимость фиксируем после короткого разбора процесса.",
  },
  engineering_rag_service: {
    id: "engineering_rag_service",
    practice: "engineering",
    title: "AI/RAG-интеграция или внутренний сервис",
    price: "от 79 000 ₽",
    description:
      "Спроектируем контур поиска по вашим данным, AI-функцию или внутренний сервис с ролями, источниками и проверяемым результатом.",
    note: "Границы проекта и итоговую оценку подтверждаем после диагностики данных и интеграций.",
  },
} as const;

export type StarterOfferId = keyof typeof starterOffers;

export const legalStarterOffers: StarterOffer[] = [
  starterOffers.legal_consultation,
  starterOffers.legal_contract_review,
  starterOffers.legal_claim_response,
];

export const engineeringStarterOffers: StarterOffer[] = [
  starterOffers.engineering_diagnostic,
  starterOffers.engineering_prototype,
  starterOffers.engineering_rag_service,
];

export function getStarterOffer(
  id: unknown,
  practice?: StarterOfferPractice,
): StarterOffer | undefined {
  if (typeof id !== "string" || !(id in starterOffers)) return undefined;
  const offer = starterOffers[id as StarterOfferId];
  return !practice || offer.practice === practice ? offer : undefined;
}

export function addStarterOfferToMessage(
  message: string,
  id: unknown,
  practice?: StarterOfferPractice,
): string {
  const offer = getStarterOffer(id, practice);
  if (!offer) return message;
  const heading = `Выбранный формат: ${offer.title} — ${offer.price}.`;
  return message.trim() ? `${heading}\n\n${message.trim()}` : heading;
}

declare global {
  interface WindowEventMap {
    starter_offer_selected: CustomEvent<{ offerId: StarterOfferId }>;
  }
}
