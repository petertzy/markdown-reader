import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const ts = require("typescript");
const PANELS = { PREVIEW: "preview", AI: "ai", CITATION: "citation" };

function compile(path) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
}

function load(compiled, react, jsxRuntime = {}) {
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    require(name) {
      if (name === "react") return react;
      if (name === "@/types/panels") return { PANELS };
      if (name === "react/jsx-runtime") return jsxRuntime;
      throw new Error(`Unexpected import: ${name}`);
    },
  });
  return exports;
}

function renderPanels() {
  let activePanel;
  const react = {
    useState(initial) {
      if (activePanel === undefined) activePanel = initial;
      return [activePanel, (next) => {
        activePanel = typeof next === "function" ? next(activePanel) : next;
      }];
    },
    useCallback(callback) { return callback; },
  };
  const { usePanels } = load(compile("../frontend/src/hooks/usePanels.ts"), react);
  return { controller: usePanels(), get activePanel() { return activePanel; } };
}

function toolbarButtons(activePanel, onTogglePanel) {
  const react = {
    useState(initial) { return [initial, () => {}]; },
    useEffect() {},
  };
  const jsx = (type, props) => ({ type, props });
  const { default: Toolbar } = load(
    compile("../frontend/src/components/Toolbar.tsx"),
    react,
    { jsx, jsxs: jsx },
  );
  const tree = Toolbar({
    onOpenFile() {}, onOpenProject() {}, onSaveFile() {}, onExport() {},
    onOpenBrowserPreview() {}, onToggleDark() {}, activePanel, onTogglePanel,
    onToggleFocusMode() {}, darkMode: false, fontSize: 14,
    onFontSizeChange() {}, showFocusPanel: false,
  });
  return tree.props.children.filter((child) => child?.type === "button");
}

test("clicking each active toolbar panel again closes it", () => {
  const titles = { preview: "Preview", ai: "AI Assistant", citation: "Citations" };
  for (const panel of Object.values(PANELS)) {
    const rendered = renderPanels();
    const clickButton = () => {
      const button = toolbarButtons(rendered.activePanel, rendered.controller.togglePanel)
        .find((candidate) => candidate.props.title === titles[panel]);
      assert.ok(button, `missing toolbar button for ${panel}`);
      button.props.onClick();
    };
    if (rendered.activePanel !== panel) {
      clickButton();
      assert.equal(rendered.activePanel, panel);
    }
    clickButton();
    assert.equal(rendered.activePanel, null);
  }
});
