import { test } from "node:test";
import assert from "node:assert/strict";

import {
  isCompositionBlocked,
  shortcutMatchesEvent,
} from "../src/lib/keyboardShortcuts.ts";

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