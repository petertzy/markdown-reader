import { test } from "node:test";
import assert from "node:assert/strict";

const { revealInFileManager } = await import("../src/utils/revealInFileManager.mjs");

test("reveals a POSIX path", async () => {
  const revealed = [];
  await revealInFileManager("/Users/me/Documents/report.pdf", async (path) => { revealed.push(path); });
  assert.deepEqual(revealed, ["/Users/me/Documents/report.pdf"]);
});

test("reveals a native Windows path with backslashes", async () => {
  const revealed = [];
  const winPath = "C:\\Users\\Public\\Documents\\report.pdf";
  await revealInFileManager(winPath, async (path) => { revealed.push(path); });
  assert.deepEqual(revealed, [winPath]);
});

test("throws when no path is provided", async () => {
  let called = false;
  await assert.rejects(() => revealInFileManager("", async () => { called = true; }), /No file path provided/);
  assert.equal(called, false);
});
