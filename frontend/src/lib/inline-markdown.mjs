/**
 * inline-markdown.mjs
 * ===================
 * Splits a line of assistant prose into the inline Markdown the chat panel
 * renders: `**bold**`, `` `code` ``, `[label](https://…)` and bare
 * `https://…` links.
 *
 * Kept as a plain ESM module (no TypeScript, no React) for two reasons:
 *  - CI runs the frontend suite on Node 20, which cannot import `.ts`, so the
 *    decision has to live in a `.mjs` for `node --test` to reach the exact code
 *    the app runs (same pattern as http-timeout.mjs / preview-base-dir.mjs).
 *  - Deciding where a bare URL *ends* is pure string work, and far easier to
 *    pin down here than through React rendering.
 */

// Captures strong, code, link and bare-URL, in that order of preference.
// Kept as a source string and compiled per call: a module-level /g regex would
// carry `lastIndex` between calls, so two scans of the same text could disagree.
const INLINE_SOURCE =
  "(\\*\\*([^*]+)\\*\\*|`([^`]+)`|\\[([^\\]]+)\\]\\((https?:\\/\\/[^)\\s]+)\\)|(https?:\\/\\/[^\\s]+))";

// Punctuation and quotes that belong to the surrounding prose. A URL that runs
// straight into one of these ends before it.
const TRAILING_PUNCTUATION = "?!.,:;*_~'\"";

const BRACKET_PAIRS = { ")": "(", "]": "[", "}": "{" };

/**
 * The URL text a bare link should actually cover.
 *
 * `[^\s]+` runs to the next space, so it also swallows whatever sentence
 * punctuation follows the URL: in "See https://example.com." the trailing "."
 * is prose, and folding it into the href produces a dead link. Closing
 * brackets are the exception and are settled by balance rather than by
 * character, because RFC 3986 allows them inside a path: "…/a(b)" must stay
 * whole while the ")" that merely closes a surrounding "(see …)" must not.
 *
 * The two rules are alternated rather than run in sequence, because either can
 * uncover the other: in "https://a.io)," the "," has to come off before the
 * stray ")" is visible, and dropping the bracket pass first would leave that ")"
 * behind in the href. `end` only ever decreases, so this terminates.
 *
 * @param {string} url Raw text matched by the bare-URL branch.
 * @returns {string} The URL with prose punctuation and unbalanced closers removed.
 */
export function bareUrlSpan(url) {
  let end = url.length;

  for (;;) {
    const last = url[end - 1];
    if (last === undefined) break;

    if (TRAILING_PUNCTUATION.includes(last)) {
      end -= 1;
      continue;
    }

    const opener = BRACKET_PAIRS[last];
    if (opener !== undefined) {
      const head = url.slice(0, end);
      const closes = head.split(last).length - 1;
      if (closes > head.split(opener).length - 1) {
        end -= 1;
        continue;
      }
    }

    break;
  }

  return url.slice(0, end);
}

/**
 * Tokenize one line of assistant prose.
 *
 * Text runs between matches are returned verbatim as `text` tokens so the
 * caller can emit them as bare strings, exactly as the panel did when this
 * scan lived inline. Returns an empty array for empty input.
 *
 * @param {string} text
 * @returns {Array<{type: "text", value: string}
 *   | {type: "strong", value: string}
 *   | {type: "code", value: string}
 *   | {type: "link", label: string, href: string}>}
 */
export function tokenizeInlineMarkdown(text) {
  const tokens = [];
  if (!text) return tokens;

  const pattern = new RegExp(INLINE_SOURCE, "g");

  let lastIndex = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }

    if (match[2]) {
      tokens.push({ type: "strong", value: match[2] });
    } else if (match[3]) {
      tokens.push({ type: "code", value: match[3] });
    } else if (match[5]) {
      // Authored as `[label](url)`, so the closing paren already delimited it.
      tokens.push({ type: "link", label: match[4], href: match[5] });
    } else {
      const raw = match[6];
      const href = bareUrlSpan(raw);
      tokens.push({ type: "link", label: href, href });
      // Whatever bareUrlSpan gave back is prose that the /g match swallowed,
      // so it has to be re-emitted or the sentence loses its punctuation.
      if (href.length < raw.length) {
        tokens.push({ type: "text", value: raw.slice(href.length) });
      }
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIndex) });
  }

  return tokens;
}