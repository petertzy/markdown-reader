// setup-monaco.mjs
// Polyfills and loaders required to load Monaco Editor in Node environment for regression tests.

globalThis.window = {
  addEventListener: () => {},
  removeEventListener: () => {},
  matchMedia: () => ({
    matches: false,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
  }),
  location: { href: "http://localhost" },
};
globalThis.self = globalThis.window;
globalThis.document = {
  querySelector: () => null,
  createElement: () => ({ setAttribute: () => {}, appendChild: () => {} }),
  head: { appendChild: () => {} },
  body: { appendChild: () => {} },
};

import { register } from "node:module";
register(
  "data:text/javascript," +
    encodeURIComponent(`
export function load(url, context, defaultLoad) {
  if (url.endsWith('.css')) {
    return { format: 'module', shortCircuit: true, source: 'export default {};' };
  }
  return defaultLoad(url, context);
}
`)
);
