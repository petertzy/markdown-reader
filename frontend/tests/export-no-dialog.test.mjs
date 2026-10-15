import { test, mock } from "node:test";
import assert from "node:assert/strict";

// Mock de Tauri (ajusta la ruta si tu build de test usa otro alias)
const invokeMock = mock.fn(async () => undefined);
mock.module("@tauri-apps/api/core", {
  namedExports: { invoke: invokeMock },
});

// Mock de fetch para el backend
global.fetch = mock.fn(async () => ({
  ok: true,
  json: async () => ({ path: "/tmp/exported.pdf" }),
}));

// Espías sobre APIs del navegador que NO deberían llamarse
const alertSpy = mock.fn();
const confirmSpy = mock.fn();
global.alert = alertSpy;
global.confirm = confirmSpy;

const { renderHook, act } = await import("@testing-library/react");
const { useFileIO } = await import("../src/hooks/useFileIO.ts");

test("export does not trigger alert or confirm dialog", async () => {
  const editor = {
    activeTab: { content: "# Hi", filePath: "/tmp/doc.md", id: "t1" },
    showToast: mock.fn(),
  };
  const { result } = renderHook(() =>
    useFileIO({ editor, isDesktopRuntime: true, backendStatus: "ready", monacoRef: { current: null } })
  );

  await act(async () => {
    await result.current.handleExport();
  });

  assert.equal(alertSpy.mock.callCount(), 0, "alert() should not be called");
  assert.equal(confirmSpy.mock.callCount(), 0, "confirm() should not be called");
});