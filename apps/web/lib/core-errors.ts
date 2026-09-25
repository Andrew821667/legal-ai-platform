/**
 * Ошибки ядра — по-русски, для юриста и клиента.
 *
 * Ядро отвечает отказами по-английски («Only a signed agreement takes a
 * supplement…»), и они доходили до экрана как есть: юрист видел английскую
 * строку там, где ждал объяснения. Ядро оставляет свои тексты — на них
 * завязаны тесты и боты, — а переводит их сайт, в одном месте, по дороге к
 * экрану. Неизвестный текст остаётся как есть: лучше английская правда, чем
 * выдуманная русская.
 */

const EXACT: Record<string, string> = {
  // Не найдено
  "Lead not found": "Клиент не найден.",
  "Client not found": "Клиент не найден.",
  "Legal intake not found": "Обращение не найдено.",
  "Intake not found": "Обращение не найдено.",
  "Agreement not found": "Договор не найден.",
  "Main agreement not found": "Основной договор не найден.",
  "Act not found": "Акт не найден.",
  "NDA not found": "Соглашение о конфиденциальности не найдено.",
  "Consent not found": "Согласие на обработку ПД не найдено.",
  "Document not found": "Документ не найден.",
  "Link not found": "Связь не найдена.",
  "Delivery not found": "Отправка не найдена.",
  "Template not found": "Заготовка не найдена.",

  // Договор
  "Client has no Telegram": "У клиента нет диалога с ботом в Telegram — отправить некуда.",
  "Client has no Telegram dialog": "У клиента нет диалога с ботом в Telegram — отправить некуда.",
  "Bot token is not configured": "Сервер не настроен: нет токена бота.",
  "NDA must be signed first": "Сначала клиент должен подписать соглашение о конфиденциальности.",
  "NDA must be signed before uploading documents": "Документы принимаются после подписания NDA.",
  "Conflict check must be clear": "Сначала отметьте, что конфликта интересов нет.",
  "Conflict check must be clear first": "Сначала отметьте, что конфликта интересов нет.",
  "Operator contract details are incomplete": "Не заполнены реквизиты исполнителя — договор составить нельзя.",
  "A signed agreement cannot be replaced; create a new intake":
    "Подписанный договор не заменяется новой редакцией. Для новых условий — допсоглашение или новое обращение.",
  "A newer agreement revision already exists": "Уже есть более новая редакция договора.",
  "Only a draft can be sent": "Отправить можно только черновик.",
  "Agreement is not a draft": "Договор уже отправлен — это не черновик.",
  "Agreement draft is not awaiting details": "Этот договор не ждёт реквизитов клиента.",
  "Client details must be completed first": "Сначала нужно заполнить реквизиты.",
  "Client details are already completed": "Реквизиты уже заполнены.",
  "Agreement is not available for viewing": "Договор сейчас недоступен для просмотра.",
  "Agreement must be viewed before signing": "Сначала откройте и прочитайте документ.",
  "Agreement cannot be declined": "От этого договора уже нельзя отказаться.",
  "Agreement is not open for questions": "По этому договору вопросы уже не принимаются.",
  "Agreement belongs to another client": "Этот договор принадлежит другому клиенту.",
  "Document hash mismatch": "Документ изменился с момента открытия — откройте его заново.",
  "Position and authority basis are required": "Укажите должность и основание полномочий.",
  "Case already has an agreement": "По делу уже есть договор.",
  "Reopen the case explicitly first": "Сначала откройте дело заново.",

  // Допсоглашение и сумма
  "Only a signed agreement takes a supplement; change an unsigned one with a new revision":
    "Допсоглашение — только к подписанному договору. Неподписанный меняется новой редакцией.",
  "A supplement is added to the main agreement": "Допсоглашение добавляется к основному договору.",
  "Supplement amount is set by its document": "Сумму допсоглашения задаёт его документ.",
  "Amount is already set; change it with a new revision or a supplementary agreement":
    "Сумма уже указана. Изменить её можно новой редакцией или допсоглашением.",

  // Акты
  "Act can only be issued for a signed agreement": "Акт выставляется только по подписанному договору.",
  "Issue the act under the main agreement": "Акт выставляется по основному договору, а не по допсоглашению.",
  "Act is not a draft": "Акт уже отправлен — это не черновик.",
  "Act is not awaiting payment": "Акт не ждёт оплаты.",
  "Accepted or paid act cannot be cancelled": "Принятый или оплаченный акт отозвать нельзя.",
  "Act is unavailable or document changed": "Акт недоступен или изменился — откройте его заново.",
  "Read the act first": "Сначала откройте и прочитайте акт.",
  "Act already accepted; contact the operator": "Акт уже принят. По вопросам — напишите юристу.",
  "Objections already recorded; contact the operator": "Замечания уже переданы. По вопросам — напишите юристу.",
  "Resolve objections and issue a new act first": "Сначала разберите замечания и выставьте новый акт.",
  "Describe completed work": "Опишите выполненную работу.",
  "Describe objections": "Опишите замечания.",
  "Not the client of this act": "Этот акт выставлен другому клиенту.",
  "Payment reminder was already sent today": "Сегодня уже напоминали — следующее напоминание можно завтра.",
  "This revision can only be signed in Telegram":
    "Эту редакцию можно подписать только в Telegram. Попросите юриста прислать новую редакцию — её можно будет подписать в кабинете.",
  "Client account does not own this lead": "Это обращение оставлено с другой почтой.",
  "Consent belongs to another client": "Согласие дано другим клиентом.",
  "Receipt is recorded for a paid act": "Чек записывается только для оплаченного акта.",
  "Receipt link is required to send it": "Чтобы отправить чек клиенту, вставьте ссылку на него из «Мой налог».",

  // Архив, отправки
  "Move the client to the archive first": "Сначала уберите клиента в архив.",
  "Send it again from the client card": "Договор, ответ и акт отправляются заново из карточки клиента.",

  // Доступ
  "Missing X-API-Key": "Сервер не настроен: нет ключа доступа к ядру.",
  "Invalid API key": "Сервер не настроен: ключ доступа к ядру не подошёл.",
  "Insufficient scope": "Не хватает прав на это действие.",
  "Too many invalid API key attempts": "Слишком много неверных попыток доступа — подождите немного.",

  // Клиентские данные
  "personal data consent is required": "Нужно согласие на обработку персональных данных.",
  "valid personal data consent is required": "Нужно действующее согласие на обработку персональных данных.",
  "document changed since it was shown to the signer": "Документ изменился — откройте его заново.",
  "consent changed since it was shown to the signer": "Текст согласия изменился — откройте его заново.",
  "Consent belongs to another Telegram user": "Согласие дано с другого аккаунта Telegram.",
  "Telegram user does not own this lead": "Это обращение принадлежит другому аккаунту Telegram.",
  "text is required": "Напишите текст.",
};

const PREFIX: [string, string][] = [
  ["Telegram delivery failed", "Telegram не принял сообщение. Проверьте связь и попробуйте ещё раз."],
  ["Contract AI unreachable", "Сервис анализа договоров сейчас недоступен."],
];

/** Поля форм — для ошибок проверки (422). */
const FIELDS: Record<string, string> = {
  subject: "«Предмет»",
  scope_text: "«Что входит»",
  exclusions_text: "«Не входит»",
  schedule_text: "«Сроки»",
  price_text: "«Стоимость»",
  amount_minor: "«Сумма к учёту»",
  payment_terms: "«Оплата»",
  name: "«Название»",
  text: "«Текст»",
  reason: "«Причина»",
  description_text: "«Описание работы»",
  full_name: "«ФИО»",
  contact: "«Контакт»",
  address: "«Адрес»",
  inn: "«ИНН»",
  ogrn: "«ОГРН»",
};

type ValidationItem = { loc?: unknown[]; msg?: string };

function validationText(items: ValidationItem[]): string {
  const fields = new Set<string>();
  for (const item of items) {
    const loc = Array.isArray(item.loc) ? item.loc : [];
    const key = String(loc[loc.length - 1] ?? "");
    fields.add(FIELDS[key] || key);
  }
  const list = [...fields].filter(Boolean);
  return list.length ? `Проверьте поля: ${list.join(", ")}.` : "Проверьте введённые данные.";
}

/** Текст ошибки ядра по-русски; неизвестное — как есть. */
export function translateCoreDetail(detail: unknown): unknown {
  if (Array.isArray(detail)) return validationText(detail as ValidationItem[]);
  if (typeof detail !== "string") return detail;
  const text = detail.trim();
  if (EXACT[text]) return EXACT[text];
  for (const [prefix, russian] of PREFIX) {
    if (text.startsWith(prefix)) return russian;
  }
  return detail;
}

/** Тело неуспешного ответа ядра — с переведённым detail; остальное как есть. */
export function translateCoreErrorBody(raw: string): string {
  try {
    const body = JSON.parse(raw) as unknown;
    if (body && typeof body === "object" && "detail" in body) {
      const record = body as Record<string, unknown>;
      return JSON.stringify({ ...record, detail: translateCoreDetail(record.detail) });
    }
  } catch {
    // Не JSON — отдаём как пришло.
  }
  return raw;
}
