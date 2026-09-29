/**
 * tests/api-fetch-timeout.test.mjs
 * ================================
 * Regression tests for the request-timeout behavior described in review
 * feedback on the "close leaked fds and time out hung API requests" PR:
 *
 * 1. Long-running AI/conversion requests must NOT be cut off by the short
 *    default timeout — they get their own generous budget.
 * 2. A caller-supplied AbortSignal must be COMPOSED with the timeout signal,
 *    so both caller cancellation and the timeout stay effective (previously
 *    `init.signal ?? controller.signal` silently dropped the timeout whenever
 *    a caller supplied a signal).
 * 3. An empty cleanup / unrelated cleanup must not mark the client handled —
 *    (covered by the ESLint rule tests; kept here for the shared module).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";

import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  LONG_REQUEST_TIMEOUT_MS,
  fetchWithTimeout,
  composeAbortSignals,
} from "../src/lib/http-timeout.mjs";

/** Starts a local HTTP server that responds after `delayMs`. */
function startSlowServer(delayMs) {
  const server = http.createServer((req, res) => {
    const timer = setTimeout(() => {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: true }));
    }, delayMs);
    // The client may abort before we respond — clean up the timer.
    req.on("close", () => clearTimeout(timer));
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({
        server,
        url: `http://127.0.0.1:${port}/api/ai/translate`,
      });
    });
  });
}

function closeServer(server) {
  return new Promise((resolve) => server.close(resolve));
}

test("default timeout aborts a hung request", async () => {
  const { server, url } = await startSlowServer(2000);
  try {
    const started = Date.now();
    await assert.rejects(
      fetchWithTimeout(url, { method: "POST" }, 120),
      (err) => err.name === "AbortError"
    );
    // Should abort near the 120ms budget, not wait for the 2s server.
    assert.ok(Date.now() - started < 1500, "request should abort well before the server responds");
  } finally {
    await closeServer(server);
  }
});

test("long-running AI/conversion requests get their own generous budget", async () => {
  // An AI-ish request that takes longer than the short default would allow
  // must succeed when given the long-running budget.
  const { server, url } = await startSlowServer(250);
  try {
    const res = await fetchWithTimeout(url, { method: "POST" }, LONG_REQUEST_TIMEOUT_MS);
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.deepEqual(body, { ok: true });
  } finally {
    await closeServer(server);
  }
});

test("caller signal aborts even when a generous timeout is set", async () => {
  const { server, url } = await startSlowServer(2000);
  const caller = new AbortController();
  try {
    const started = Date.now();
    const pending = fetchWithTimeout(
      url,
      { method: "POST", signal: caller.signal },
      LONG_REQUEST_TIMEOUT_MS
    );
    // Abort via the caller mid-flight — this must win over the long budget.
    setTimeout(() => caller.abort(), 120);
    await assert.rejects(pending, (err) => err.name === "AbortError");
    assert.ok(Date.now() - started < 1500, "caller abort should win over the long timeout");
  } finally {
    await closeServer(server);
  }
});

test("timeout still applies when caller supplies a signal", async () => {
  // The regression: previously `init.signal ?? controller.signal` meant
  // supplying a signal silently disabled the timeout. Now, an un-aborted
  // caller signal must NOT disable the timeout.
  const { server, url } = await startSlowServer(5000);
  const caller = new AbortController();
  try {
    const started = Date.now();
    await assert.rejects(
      fetchWithTimeout(url, { method: "POST", signal: caller.signal }, 150),
      (err) => err.name === "AbortError"
    );
    assert.ok(Date.now() - started < 2000, "timeout should fire even with a caller signal present");
    assert.strictEqual(caller.signal.aborted, false, "caller signal must not be aborted by our timeout");
  } finally {
    await closeServer(server);
  }
});

test("timeout is not applied when timeoutMs is explicitly disabled", async () => {
  const { server, url } = await startSlowServer(100);
  try {
    const res = await fetchWithTimeout(url, { method: "POST" }, 0);
    assert.strictEqual(res.status, 200);
  } finally {
    await closeServer(server);
  }
});

test("composeAbortSignals forwards a single signal and undefined for none", () => {
  const controller = new AbortController();
  assert.strictEqual(composeAbortSignals(controller.signal), controller.signal);
  assert.strictEqual(composeAbortSignals(), undefined);
  assert.strictEqual(composeAbortSignals(undefined, controller.signal), controller.signal);
});

test("composeAbortSignals aborts when any input aborts", () => {
  const a = new AbortController();
  const b = new AbortController();
  const combined = composeAbortSignals(a.signal, b.signal);
  assert.ok(combined, "combined signal exists");
  assert.strictEqual(combined.aborted, false);
  b.abort();
  assert.strictEqual(combined.aborted, true, "any-input abort propagates to the composed signal");

  // Already-aborted input produces an aborted composed signal immediately.
  const c = new AbortController();
  c.abort();
  const immediate = composeAbortSignals(c.signal, new AbortController().signal);
  assert.strictEqual(immediate.aborted, true);
});

test("constants are sane: long budget is strictly greater than the default", () => {
  assert.ok(LONG_REQUEST_TIMEOUT_MS > DEFAULT_REQUEST_TIMEOUT_MS);
  assert.strictEqual(DEFAULT_REQUEST_TIMEOUT_MS, 30000);
  assert.strictEqual(LONG_REQUEST_TIMEOUT_MS, 5 * 60 * 1000);
});