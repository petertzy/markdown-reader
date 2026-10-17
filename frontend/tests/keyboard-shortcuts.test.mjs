import { test } from "node:test";
import assert from "node:assert/strict";

// NOTE: These helpers deliberately mirror `frontend/src/lib/keyboardShortcuts.ts`
// (`shortcutMatchesEvent` and `isCompositionBlocked`) as a self-contained copy.
// CI runs the frontend suite on Node 20, which cannot import `.ts` modules, so we
// keep this regression test dependency-free (same approach as editor-undo.test.mjs).
// Keep this file's logic in sync with keyboardShortcuts.ts.

function shortcutMatchesEvent(binding, event) {
  const keyMatches = String(event.key).toLowerCase() === String(binding.key).toLowerCase();
  const codeMatches = Boolean(binding.code && event.code === binding.code);
  return (
    (keyMatches || codeMatches) &&
    event.ctrlKey === Boolean(binding.ctrl) &&
    event.metaKey === Boolean(binding.meta) &&
    event.shiftKey === Boolean(binding.shift) &&
    event.altKey === Boolean(binding.alt)
  );
}

function isCompositionBlocked(binding, event) {
  return Boolean(event.isComposing) && Boolean(binding.alt);
}

// Build a plain KeyboardEvent-like object. `chord` is the physical code, e.g. "KeyT".
function keyEvent(
  chord,
  { ctrlKey = false, metaKey = false, shiftKey = false, altKey = false, isComposing = false } = {}
) {
  const last = chord.slice(-1);
  return { key: last.toLowerCase(), code: chord, ctrlKey, metaKey, shiftKey, altKey, isComposing };
}

// An AltGr-style chord on Windows is reported as ctrl + alt.
const altGr = (chord, extra = {}) => keyEvent(chord, { ctrlKey: true, altKey: true, ...extra });

// Mirrors the hook's decision: a binding fires only if it matches the event AND
// is not blocked by an in-progress IME composition.
const bindingFires = (binding, ev) =>
  !isCompositionBlocked(binding, ev) && shortcutMatchesEvent(binding, ev);

// Windows-style bindings (physical `code` matching is platform-independent).
const insertTable = { key: "t", code: "KeyT", ctrl: true, alt: true }; // Ctrl+Alt+T
const plain = { key: "s", code: "KeyS", ctrl: true }; // Ctrl+S (no Alt)

test("the risky match exists: an AltGr chord matches Ctrl+Alt+T by physical code", () => {
  assert.ok(
    shortcutMatchesEvent(insertTable, altGr("KeyT")),
    "Ctrl+Alt+T matches ctrl+alt + code KeyT"
  );
});

test("regression: a genuine composing Ctrl+Alt chord cannot fire table.insert", () => {
  const composing = altGr("KeyT", { isComposing: true });
  assert.ok(
    isCompositionBlocked(insertTable, composing),
    "an Alt-involving binding is blocked during genuine composition"
  );
  assert.ok(
    !bindingFires(insertTable, composing),
    "Ctrl+Alt+T must NOT fire while genuinely composing"
  );
});

test("packaged-WebKit fix preserved: a non-Alt Ctrl chord still fires when isComposing is a false positive", () => {
  const falsePositive = keyEvent("KeyS", { ctrlKey: true, isComposing: true });
  assert.ok(
    !isCompositionBlocked(plain, falsePositive),
    "a non-Alt binding is trusted through a spurious isComposing flag"
  );
  assert.ok(bindingFires(plain, falsePositive), "Ctrl+S still fires (packaged fix)");
});

test("non-composing Alt chord still fires normally", () => {
  assert.ok(!isCompositionBlocked(insertTable, altGr("KeyT")));
  assert.ok(bindingFires(insertTable, altGr("KeyT")), "Ctrl+Alt+T fires when not composing");
});

// ── Scope gate ───────────────────────────────────────────────────────────────
// Mirrors the dispatch gate in `frontend/src/hooks/editor/useKeyboardShortcuts.ts`
// together with `isEditableTarget` from `keyboardShortcuts.ts`:
//
//   if (shortcut.scope === "editor" && editableTarget && !isMonacoTarget) return;
//
// `edit.undo` / `edit.redo` are mapped to `runMonacoAction("undo" | "redo")`,
// which calls `mono.focus()` before triggering the editor action, so firing
// them from one of the app's own text fields hijacks focus into the document.

const TEXTAREA = { tagName: "TEXTAREA", isContentEditable: false };
const TEXT_INPUT = { tagName: "INPUT", isContentEditable: false };
const MONACO = { tagName: "DIV", isContentEditable: false, inMonaco: true };
const APP_BACKGROUND = { tagName: "DIV", isContentEditable: false, inMonaco: false };

function isEditableTarget(target) {
  if (!target || typeof target.tagName !== "string") return false;
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || target.isContentEditable === true;
}

function isMonacoTarget(target) {
  return Boolean(target && target.inMonaco);
}

/** Mirrors the hook: does this shortcut actually run its action? */
function shortcutFires(shortcut, ev, target) {
  if (!shortcut.bindings.some((b) => bindingFires(b, ev))) return false;
  const editableTarget = isEditableTarget(target);
  const monacoTarget = isMonacoTarget(target);
  if (shortcut.scope === "editor" && editableTarget && !monacoTarget) return false;
  return true;
}

const cmdZ = { key: "z", code: "KeyZ", meta: true };
const undoShortcut = { id: "edit.undo", scope: "editor", bindings: [cmdZ] };
const saveShortcut = { id: "file.save", scope: "global", bindings: [{ key: "s", code: "KeyS", meta: true }] };
const cmdS = keyEvent("KeyS", { metaKey: true });

test("regression: Cmd+Z inside the AI panel textarea does not hijack the document editor", () => {
  const ev = keyEvent("KeyZ", { metaKey: true });
  assert.ok(shortcutMatchesEvent(cmdZ, ev), "the chord still matches the binding");
  assert.ok(
    !shortcutFires(undoShortcut, ev, TEXTAREA),
    "undo must not fire from a textarea, so the field keeps its native undo"
  );
});

test("Cmd+Z inside a settings input does not hijack the document editor", () => {
  const ev = keyEvent("KeyZ", { metaKey: true });
  assert.ok(!shortcutFires(undoShortcut, ev, TEXT_INPUT));
});

test("Cmd+Z inside Monaco still undoes the document", () => {
  const ev = keyEvent("KeyZ", { metaKey: true });
  assert.ok(
    shortcutFires(undoShortcut, ev, MONACO),
    "editor-scoped shortcuts must still fire inside the document editor"
  );
});

test("Cmd+Z from the app background still reaches the document editor", () => {
  const ev = keyEvent("KeyZ", { metaKey: true });
  assert.ok(shortcutFires(undoShortcut, ev, APP_BACKGROUND));
});

test("genuinely global shortcuts are still blocked-free inside text fields", () => {
  // file.save is intentionally global: Cmd+S must keep saving the document even
  // while the AI panel's textarea has focus.
  assert.ok(
    shortcutFires(saveShortcut, cmdS, TEXTAREA),
    "scope: \"global\" commands ignore the editable-target gate"
  );
});