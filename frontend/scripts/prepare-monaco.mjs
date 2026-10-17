import { cpSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const source = resolve(dirname(require.resolve("monaco-editor/package.json")), "min/vs");
const destination = fileURLToPath(new URL("../public/monaco/vs/", import.meta.url));

// Ship the matching loader, languages, worker, CSS and codicon font together.
mkdirSync(destination, { recursive: true });
cpSync(source, destination, { recursive: true });
console.log("Prepared local Monaco assets.");
