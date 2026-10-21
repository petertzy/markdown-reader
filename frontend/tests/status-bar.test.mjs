import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const nodeRequire = createRequire(import.meta.url);
const filename = new URL("../src/components/StatusBar.tsx", import.meta.url);
const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function renderStatusBar(stats) {
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    require(name) {
      if (name === "react/jsx-runtime") return nodeRequire("react/jsx-runtime");
      throw new Error(`Unexpected StatusBar dependency: ${name}`);
    },
  }, { filename: filename.pathname });
  return renderToStaticMarkup(React.createElement(exports.default, {
    stats,
    filePath: "/notes/draft.md",
    dirty: false,
  }));
}

test("renders the heading count with the other document statistics", () => {
  const html = renderStatusBar({
    words: 1250,
    chars_with_spaces: 7430,
    chars_without_spaces: 6200,
    heading_count: 16,
    reading_time: "6 min read",
  });

  assert.match(html, /1250 words/);
  assert.match(html, /7430 chars/);
  assert.match(html, /16 headings/);
  assert.match(html, /6 min read/);
});

test("renders no statistics until they are available", () => {
  const html = renderStatusBar(null);

  assert.doesNotMatch(html, /words|chars|headings|min read/);
});
