import { test, mock } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  LONG_REQUEST_TIMEOUT_MS,
  composeAbortSignals,
  fetchWithTimeout,
  runWithTimeout,
} from "../src/lib/http-timeout.mjs";

function delayedFetch(delayMs) {
  return (_input, { signal }) =>
    new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      const timer = setTimeout(() => resolve(new Response("ok")), delayMs);
      signal.addEventListener("abort", () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      }, { once: true });
    });
}

test("default timeout aborts a hung request", async () => {
  const fetchMock = mock.method(globalThis, "fetch", delayedFetch(200));
  try {
    await assert.rejects(fetchWithTimeout("/api/test", {}, 10), { name: "AbortError" });
  } finally {
    fetchMock.mock.restore();
  }
});

test("long-running requests can use a larger budget", async () => {
  const fetchMock = mock.method(globalThis, "fetch", delayedFetch(30));
  try {
    const response = await fetchWithTimeout("/api/test", {}, LONG_REQUEST_TIMEOUT_MS);
    assert.equal(await response.text(), "ok");
  } finally {
    fetchMock.mock.restore();
  }
});

test("caller cancellation works with a deadline", async () => {
  const caller = new AbortController();
  const fetchMock = mock.method(globalThis, "fetch", delayedFetch(200));
  try {
    const pending = fetchWithTimeout("/api/test", { signal: caller.signal }, 100);
    caller.abort();
    await assert.rejects(pending, { name: "AbortError" });
  } finally {
    fetchMock.mock.restore();
  }
});

test("deadline works with a caller signal", async () => {
  const caller = new AbortController();
  const fetchMock = mock.method(globalThis, "fetch", delayedFetch(200));
  try {
    await assert.rejects(
      fetchWithTimeout("/api/test", { signal: caller.signal }, 10),
      { name: "AbortError" }
    );
    assert.equal(caller.signal.aborted, false);
  } finally {
    fetchMock.mock.restore();
  }
});

test("a zero budget disables the deadline", async () => {
  const fetchMock = mock.method(globalThis, "fetch", delayedFetch(30));
  try {
    assert.equal((await fetchWithTimeout("/api/test", {}, 0)).status, 200);
  } finally {
    fetchMock.mock.restore();
  }
});

test("deadline remains active while reading the response body", async () => {
  await assert.rejects(
    runWithTimeout(async (signal) => {
      await Promise.resolve(); // Response headers have arrived.
      return new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
    }, undefined, 10),
    { name: "AbortError" }
  );
});

test("composeAbortSignals handles absent, single, and aborted inputs", () => {
  const a = new AbortController();
  const b = new AbortController();
  assert.equal(composeAbortSignals(), undefined);
  assert.equal(composeAbortSignals(a.signal), a.signal);
  const combined = composeAbortSignals(a.signal, b.signal);
  b.abort();
  assert.equal(combined.aborted, true);
  assert.equal(composeAbortSignals(b.signal, a.signal).aborted, true);
});

test("long budget exceeds the short default", () => {
  assert.equal(DEFAULT_REQUEST_TIMEOUT_MS, 30000);
  assert.equal(LONG_REQUEST_TIMEOUT_MS, 300000);
});
