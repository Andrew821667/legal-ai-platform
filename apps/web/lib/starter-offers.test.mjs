import test from "node:test";
import assert from "node:assert/strict";

import {
  addStarterOfferToMessage,
  engineeringStarterOffers,
  getStarterOffer,
  legalStarterOffers,
  packageFields,
  packagesForPractice,
} from "./starter-offers.ts";

test("keeps three distinct offers for each practice", () => {
  assert.equal(legalStarterOffers.length, 3);
  assert.equal(engineeringStarterOffers.length, 3);
  assert.equal(new Set([...legalStarterOffers, ...engineeringStarterOffers].map((offer) => offer.id)).size, 6);
});

test("adds the canonical selected offer to a lead message", () => {
  const result = addStarterOfferToMessage(
    "Нужен разбор процесса и план внедрения.",
    "engineering_diagnostic",
    "engineering",
  );

  assert.match(result, /Выбранный формат: Диагностика автоматизации — 7 900 ₽\./);
  assert.match(result, /Нужен разбор процесса/);
});

test("rejects an offer from the wrong practice", () => {
  assert.equal(getStarterOffer("legal_consultation", "engineering"), undefined);
  assert.equal(
    addStarterOfferToMessage("Описание задачи", "legal_consultation", "engineering"),
    "Описание задачи",
  );
});

test("ignores an unknown offer id", () => {
  assert.equal(getStarterOffer("made_up_offer"), undefined);
  assert.equal(addStarterOfferToMessage("Текст", "made_up_offer"), "Текст");
});

test("пакет уходит в ядро снимком: id, название и цена, которые видел клиент", () => {
  assert.deepEqual(packageFields(getStarterOffer("legal_contract_review")), {
    package_id: "legal_contract_review",
    package_title: "Экспресс-проверка договора",
    package_price_text: "от 7 900 ₽",
  });
  assert.deepEqual(packageFields(undefined), {});
  assert.equal(packagesForPractice("legal").length, 3);
  assert.equal(packagesForPractice("hybrid").length, 6);
});
