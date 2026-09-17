import assert from "node:assert/strict";
import { test } from "node:test";

import { safeNextPath } from "./cabinet-redirect.ts";

test("обычный относительный путь пропускается как есть", () => {
  assert.equal(safeNextPath("/cabinet/profile"), "/cabinet/profile");
});

test("пусто или не задано — дефолтный /cabinet", () => {
  assert.equal(safeNextPath(""), "/cabinet");
  assert.equal(safeNextPath(null), "/cabinet");
  assert.equal(safeNextPath(undefined), "/cabinet");
});

test("protocol-relative //evil.com отклоняется (это переход на чужой хост)", () => {
  assert.equal(safeNextPath("//evil.example"), "/cabinet");
});

test("абсолютный URL с протоколом отклоняется", () => {
  assert.equal(safeNextPath("https://evil.example/phish"), "/cabinet");
  assert.equal(safeNextPath("http://evil.example"), "/cabinet");
});

test("путь без ведущего слэша отклоняется", () => {
  assert.equal(safeNextPath("evil.example"), "/cabinet");
  assert.equal(safeNextPath("cabinet/profile"), "/cabinet");
});

test("обратный слэш в пути отклоняется (браузерная путаница /\\ с //)", () => {
  assert.equal(safeNextPath("/\\evil.example"), "/cabinet");
  assert.equal(safeNextPath("/a\\b"), "/cabinet");
});

test("пробелы и управляющие символы отклоняются", () => {
  assert.equal(safeNextPath("/cabinet profile"), "/cabinet");
  assert.equal(safeNextPath("/cabinet\tprofile"), "/cabinet");
  assert.equal(safeNextPath("/cabinet\nprofile"), "/cabinet");
});

test("слишком длинное значение отклоняется", () => {
  assert.equal(safeNextPath(`/${"a".repeat(600)}`), "/cabinet");
});

test("путь с query-строкой пропускается", () => {
  assert.equal(safeNextPath("/cabinet/profile?tab=phone"), "/cabinet/profile?tab=phone");
});
