import { test, mock } from "node:test";
import assert from "node:assert/strict";

const openMock = mock.fn(async () => undefined);
mock.module("@tauri-apps/plugin-shell", {
  namedExports: { open: openMock },
});

test("showInFinder opens the parent directory of the exported file", async () => {
  const { renderHook, act } = await import("@testing-library/react");
  const { useFileIO } = await import("../src/hooks/useFileIO.ts");

  const editor = {
    activeTab: { content: "# Hi", filePath: "/tmp/doc.md", id: "t1" },
  };
  const { result } = renderHook(() =>
    useFileIO({ editor, isDesktopRuntime: true, backendStatus: "ready", monacoRef: { current: null } })
  );

  // Simula que ya se exportó un archivo
  await act(async () => {
    result.current.setLastExportedPath?.("/Users/me/Documents/out.pdf");
  });

  await act(async () => {
    await result.current.showInFinder();
  });

  assert.equal(openMock.mock.callCount(), 1);
  assert.equal(openMock.mock.calls[0].arguments[0], "/Users/me/Documents");
});

test("showInFinder is a no-op when nothing has been exported", async () => {
  const { renderHook, act } = await import("@testing-library/react");
  const { useFileIO } = await import("../src/hooks/useFileIO.ts");

  const editor = { activeTab: { content: "", filePath: null, id: "t1" } };
  const { result } = renderHook(() =>
    useFileIO({ editor, isDesktopRuntime: true, backendStatus: "ready", monacoRef: { current: null } })
  );

  await act(async () => {
    await result.current.showInFinder();
  });

  assert.equal(openMock.mock.callCount(), 0);
});