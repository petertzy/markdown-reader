import { test, mock } from "node:test";
import assert from "node:assert/strict";

// Mock del módulo de Tauri antes de importar la utilidad
const revealItemInDirMock = mock.fn(async () => undefined);

mock.module("@tauri-apps/plugin-opener", {
  namedExports: {
    revealItemInDir: revealItemInDirMock,
  },
});

const { revealInFileManager } = await import("../src/utils/revealInFileManager.ts");

test("reveals a POSIX path", async () => {
  revealItemInDirMock.mock.resetCalls();
  await revealInFileManager("/Users/me/Documents/report.pdf");
  assert.equal(revealItemInDirMock.mock.callCount(), 1);
  assert.equal(revealItemInDirMock.mock.calls[0].arguments[0], "/Users/me/Documents/report.pdf");
});

test("reveals a native Windows path with backslashes", async () => {
  revealItemInDirMock.mock.resetCalls();
  const winPath = "C:\\Users\\Public\\Documents\\report.pdf";
  await revealInFileManager(winPath);
  assert.equal(revealItemInDirMock.mock.callCount(), 1);
  assert.equal(revealItemInDirMock.mock.calls[0].arguments[0], winPath);
});

test("throws when no path is provided", async () => {
  revealItemInDirMock.mock.resetCalls();
  await assert.rejects(() => revealInFileManager(""), /No file path provided/);
  assert.equal(revealItemInDirMock.mock.callCount(), 0);
});