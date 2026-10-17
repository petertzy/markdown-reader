import { test } from "node:test";
import assert from "node:assert/strict";
import { splitTextIntoTranslationUnits } from "../src/lib/translation-units.mjs";

// These cases mirror tests/test_translation_units.py so the client splitter and
// the canonical backend splitter (backend/ai_logic.split_text_into_translation_units)
// cannot drift apart: whatever the backend would return is what the editor must
// batch and send.

test("abbreviation keeps the sentence together", () => {
  assert.deepEqual(
    splitTextIntoTranslationUnits("Dr. Smith went home. Then he slept."),
    ["Dr. Smith went home.", "Then he slept."]
  );
});

test("dotted acronym is not split", () => {
  assert.deepEqual(
    splitTextIntoTranslationUnits("The U.S. Army won. Really."),
    ["The U.S. Army won.", "Really."]
  );
});


test("a dotted acronym outside the known set still stays together", () => {
  // "A.K." is not a listed abbreviation, so only the dotted-acronym rule keeps
  // it with the following capitalised word instead of splitting at "A.K.".
  assert.deepEqual(splitTextIntoTranslationUnits("A.K. Jones spoke."), ["A.K. Jones spoke."]);
});

test("e.g. stays with the next word", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("Please send it e.g. tomorrow."), [
    "Please send it e.g. tomorrow.",
  ]);
});

test("fig. reference is not split", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("See fig. 3 and fig. 4 at 5p.m."), [
    "See fig. 3 and fig. 4 at 5p.m.",
  ]);
});

test("a numbered sentence still splits", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("In 1994. That was the year."), [
    "In 1994.",
    "That was the year.",
  ]);
});

test("single-letter initials stay together", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("J. R. Trailing ends now. Next part."), [
    "J. R. Trailing ends now.",
    "Next part.",
  ]);
});

test("exclamation and question marks still split", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("Hello world? Yes! Bye."), [
    "Hello world?",
    "Yes!",
    "Bye.",
  ]);
});

test("closing quote stays with its sentence", () => {
  assert.deepEqual(splitTextIntoTranslationUnits('He said "Stop." Then ran.'), [
    'He said "Stop."',
    "Then ran.",
  ]);
});

test("a lowercase follow does not split a quoted fragment", () => {
  assert.deepEqual(splitTextIntoTranslationUnits('Single "quote." after.'), [
    'Single "quote." after.',
  ]);
});

test("a version number followed by a capital still splits", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("Version 1.2. Next"), [
    "Version 1.2.",
    "Next",
  ]);
});

test("a version number followed by lowercase does not split", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("Version 1.2. next"), [
    "Version 1.2. next",
  ]);
});

test("a period followed by a number does not create a sentence boundary", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("Section 1. 2 follows"), [
    "Section 1. 2 follows",
  ]);
});

test("a non-ASCII single-letter initial stays with the next word", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("É. Dupont arrived."), [
    "É. Dupont arrived.",
  ]);
});

test("CJK sentences split without spaces", () => {
  assert.deepEqual(
    splitTextIntoTranslationUnits("今天天气很好。我们去公园吧。明天再说。"),
    ["今天天气很好。", "我们去公园吧。", "明天再说。"]
  );
});

test("fenced code is kept as one unit", () => {
  assert.deepEqual(
    splitTextIntoTranslationUnits("Intro line.\n\n```js\nconst a = 1;\n```\n\nOutro."),
    ["Intro line.", "```js\nconst a = 1;\n```", "Outro."]
  );
});

test("headings and list items are their own units", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("# Title\n\n- item one\n- item two"), [
    "# Title",
    "- item one",
    "- item two",
  ]);
});

test("backend-style Markdown markers do not require a following space", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("#heading\n-item\n+item\n*item"), [
    "#heading",
    "-item",
    "+item",
    "*item",
  ]);
});

test("Unicode line separators match the backend line handling", () => {
  assert.deepEqual(splitTextIntoTranslationUnits("First.\u2028Second."), [
    "First.",
    "Second.",
  ]);
});
