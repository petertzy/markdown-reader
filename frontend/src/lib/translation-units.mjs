/**
 * Sentence splitting for sentence-by-sentence translation.
 *
 * This must agree with the backend splitter in `backend/ai_logic.py`
 * (`split_text_into_translation_units`) and its test suite
 * (`tests/test_translation_units.py`): the client batches these units and the
 * backend translates each batch verbatim, so a unit boundary that exists on
 * only one side changes what the user sees as pairs.
 */

const SENTENCE_END_CHARS = ".!?。！？";
// A full-width terminator ends a sentence whatever follows it — CJK text has no
// space after 。！？.
const CJK_SENTENCE_END_CHARS = new Set(["。", "！", "？"]);
// Closing punctuation that belongs to the sentence it terminates; a
// quoted/bracketed sentence keeps its closing quote/bracket in the same unit.
const SENTENCE_CLOSING_CHARS = new Set([
  ...'"\')]」』）】》〉〙〗〛｝］',
]);

// Abbreviations whose period does not end the sentence (mirrors the backend's
// _PERIOD_NOT_SENTENCE_END).
const PERIOD_NOT_SENTENCE_END = new Set([
  "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "rev", "gen", "col",
  "capt", "lt", "sgt", "fig", "ed", "vol", "no", "dept", "univ", "corp",
  "inc", "ltd", "co", "vs", "etc", "al", "approx", "e.g", "i.e", "u.s",
  "u.k", "a.m", "p.m",
]);

// True when the "." at `periodIndex` ends a known abbreviation, a single-letter
// initial ("J."), or a dotted acronym ("U.S.").
function isAbbreviationPeriod(text, periodIndex) {
  let start = periodIndex;
  while (start > 0 && text[start - 1] !== " " && text[start - 1] !== "\t") {
    start -= 1;
  }
  const token = text.slice(start, periodIndex).toLowerCase().replace(/\.+$/, "");
  if (!token) return false;
  return (
    PERIOD_NOT_SENTENCE_END.has(token) ||
    (token.length === 1 && /[a-z]/.test(token)) ||
    /^(?:[a-z]\.)+[a-z]?$/.test(token)
  );
}

// First non-space / non-closing-quote char from `index` on, or null.
function firstCharAfter(line, index) {
  while (index < line.length && (/\s/.test(line[index]) || "\"'`)]}".includes(line[index]))) {
    index += 1;
  }
  return index < line.length ? line[index] : null;
}

export function splitTextIntoTranslationUnits(content) {
  const text = content.trim();
  if (!text) return [];
  const units = [];
  let buffer = "";
  let inCodeBlock = false;

  const flush = () => {
    const unit = buffer.trim();
    if (unit) units.push(unit);
    buffer = "";
  };

  const lines = text.split(/\r?\n/);
  lines.forEach((line, lineIndex) => {
    const stripped = line.trim();
    if (stripped.startsWith("```")) {
      if (!inCodeBlock) {
        flush();
        buffer = line;
        inCodeBlock = true;
      } else {
        buffer += `\n${line}`;
        flush();
        inCodeBlock = false;
      }
      return;
    }
    if (inCodeBlock) {
      buffer += `${buffer ? "\n" : ""}${line}`;
      return;
    }
    if (!stripped) {
      flush();
      return;
    }
    if (/^(#{1,6}\s|>\s|[-*+]\s|\d+\.\s)/.test(stripped)) {
      flush();
      units.push(line);
      return;
    }
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const nextChar = line[index + 1] ?? "";
      buffer += char;
      const boundary =
        CJK_SENTENCE_END_CHARS.has(char) ||
        (SENTENCE_END_CHARS.includes(char) && ["", " ", "\t", "\"", "'", ")", "]"].includes(nextChar));
      if (!boundary) continue;
      let endsSentence = true;
      if (char === ".") {
        // "Dr." / "e.g." / "U.S." do not end a sentence.
        if (isAbbreviationPeriod(line, index)) {
          endsSentence = false;
        } else {
          // "Version 1.2. Next" — only split when the next word is capitalized.
          const following = firstCharAfter(line, index + 1);
          if (following !== null && following !== following.toUpperCase()) {
            endsSentence = false;
          }
        }
      }
      if (endsSentence) {
        // Absorb a closing quote/bracket into the finished unit, otherwise it
        // becomes the first character of the next one.
        while (index + 1 < line.length && SENTENCE_CLOSING_CHARS.has(line[index + 1])) {
          index += 1;
          buffer += line[index];
        }
        flush();
      }
    }
    if (lineIndex < lines.length - 1 && buffer) buffer += " ";
  });
  flush();
  return units;
}