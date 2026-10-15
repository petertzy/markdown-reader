import { test, mock } from "node:test";
import assert from "node:assert/strict";

test("Toolbar shows 'Show in Finder' only when lastExportedPath is set", async () => {
  const { render } = await import("@testing-library/react");
  const React = await import("react");
  const { default: Toolbar } = await import("../src/components/Toolbar.tsx");

  const baseProps = {
    onOpenFile: () => {}, onSaveFile: () => {}, onExport: () => {},
    onOpenBrowserPreview: () => {}, onToggleDark: () => {},
    activePanel: null, onTogglePanel: () => {}, onToggleFocusMode: () => {},
    darkMode: false, fontSize: 14, onFontSizeChange: () => {},
    showFocusPanel: false, backendStatus: "ready", backendMessage: null,
  };

  const { queryByTitle, rerender } = render(
    React.createElement(Toolbar, { ...baseProps, lastExportedPath: null, onShowInFinder: () => {} })
  );
  assert.equal(queryByTitle("Show in Finder"), null);

  rerender(
    React.createElement(Toolbar, { ...baseProps, lastExportedPath: "/tmp/out.pdf", onShowInFinder: () => {} })
  );
  assert.notEqual(queryByTitle("Show in Finder"), null);
});