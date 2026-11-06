import { test } from "node:test";
import assert from "node:assert/strict";

// Covers how the Shortcuts menu splits shortcuts into columns.
import { groupShortcuts } from "../src/lib/shortcut-groups.mjs";

const ids = (column) => column.items.map((s) => s.id);
const s = (id) => ({ id, label: id });

test("shortcuts are split into File, Edit, Format and View columns in that order", () => {
  const columns = groupShortcuts([s("view.toggleDarkMode"), s("format.bold"), s("edit.undo"), s("file.save")]);
  assert.deepEqual(columns.map((c) => c.heading), ["File", "Edit", "Format", "View"]);
});

test("table shortcuts go in the Format column", () => {
  const [format] = groupShortcuts([s("format.bold"), s("table.insert")]);
  assert.equal(format.heading, "Format");
  assert.deepEqual(ids(format), ["format.bold", "table.insert"]);
});

test("related actions sit together, e.g. headings in order and exports after save", () => {
  const [file, format] = groupShortcuts([
    s("format.heading2"),
    s("file.exportPdf"),
    s("format.bold"),
    s("file.new"),
    s("format.heading1"),
    s("file.save"),
  ]);
  assert.deepEqual(ids(file), ["file.new", "file.save", "file.exportPdf"]);
  assert.deepEqual(ids(format), ["format.bold", "format.heading1", "format.heading2"]);
});

test("actions without a preferred position keep their original order", () => {
  const [view] = groupShortcuts([s("view.fullPreview"), s("view.toggleDarkMode"), s("view.fullEditor")]);
  assert.deepEqual(ids(view), ["view.fullPreview", "view.toggleDarkMode", "view.fullEditor"]);
});

test("empty columns are left out and nothing is dropped", () => {
  const input = [s("view.toggleDarkMode"), s("mystery.action")];
  const columns = groupShortcuts(input);
  assert.deepEqual(columns.map((c) => c.heading), ["View", "Other"]);
  assert.equal(columns.flatMap((c) => c.items).length, input.length);
});
