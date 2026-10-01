import assert from "node:assert/strict";
import test from "node:test";

import { plainText } from "./plain-text.ts";

test("снимает Telegram-разметку с заголовка поста", () => {
  assert.equal(plainText("<b>Суд</b> разъяснил <i>порядок</i>"), "Суд разъяснил порядок");
});

test("раскрывает сущности и не оставляет двойных пробелов", () => {
  assert.equal(plainText("Закон &laquo;О&nbsp;данных&raquo;&#33; A&amp;B<br/>дальше"), "Закон «О данных»! A&B дальше");
});

test("пустое и непонятное остаётся безопасным", () => {
  assert.equal(plainText(""), "");
  assert.equal(plainText("&unknown; текст"), "&unknown; текст");
});
