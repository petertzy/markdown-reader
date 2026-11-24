// preview-sync-frame.js
// Runs inside the sandboxed Markdown preview iframe and talks to the editor
// window through postMessage (see src/lib/preview-sync.mjs for the other side).
//
// This is a static file rather than an inline <script> on purpose: the
// preview's srcdoc inherits the app's Content Security Policy, and in packaged
// Tauri builds that policy carries script hashes, which makes browsers ignore
// 'unsafe-inline'. Scripts loaded from the app's own origin are still allowed.
//
// Message names and timings come from data- attributes on the <script> tag,
// so preview-sync.mjs stays the single source of truth for them.
(function () {
  var script = document.currentScript;
  if (!script) return;
  var cfg = script.dataset;
  var MSG_TO_PREVIEW = cfg.msgToPreview;
  var MSG_FROM_PREVIEW = cfg.msgFromPreview;
  var MSG_PREVIEW_READY = cfg.msgPreviewReady;
  var MSG_SNAP = cfg.msgSnap;
  var ECHO_GUARD_MS = Number(cfg.echoGuardMs) || 0;
  var SNAP_GUARD_MS = Number(cfg.snapGuardMs) || 0;

  var ignoreUntil = 0;
  var snapUntil = 0;

  function el() {
    return document.scrollingElement || document.documentElement;
  }
  function maxScroll() {
    return Math.max(0, el().scrollHeight - window.innerHeight);
  }
  function pageTop(n) {
    return n.getBoundingClientRect().top + el().scrollTop;
  }

  function snap(m) {
    var hs = document.body.querySelectorAll("h1,h2,h3,h4,h5,h6");
    var docEnd = el().scrollHeight;
    var start = m.heading >= 0 && hs[m.heading] ? pageTop(hs[m.heading]) : 0;
    var next = hs[m.heading + 1] ? pageTop(hs[m.heading + 1]) : docEnd;
    var y = start + m.fraction * Math.max(0, next - start);
    var blocks = document.body.querySelectorAll("h1,h2,h3,h4,h5,h6,p,li,pre,blockquote,table,img,hr");
    var target = null;
    var best = Infinity;
    for (var i = 0; i < blocks.length; i++) {
      var d = Math.abs(pageTop(blocks[i]) - y);
      if (d < best) {
        best = d;
        target = blocks[i];
      }
    }
    if (target) y = pageTop(target);
    ignoreUntil = snapUntil = Date.now() + SNAP_GUARD_MS;
    window.scrollTo({ top: Math.max(0, y - window.innerHeight * 0.3), behavior: "smooth" });
    if (target) {
      var prev = target.style.backgroundColor;
      var prevT = target.style.transition;
      target.style.transition = "background-color 0.6s ease";
      target.style.backgroundColor = "rgba(59,130,246,0.22)";
      setTimeout(function () {
        target.style.backgroundColor = prev;
        setTimeout(function () {
          target.style.transition = prevT;
        }, 600);
      }, 500);
    }
  }

  window.addEventListener("message", function (e) {
    // Only the parent editor window may drive the preview.
    if (e.source !== parent) return;
    var m = e.data;
    if (!m) return;
    if (m.type === MSG_SNAP) {
      snap(m);
      return;
    }
    // A click can nudge the editor's scroll; don't let that cancel the glide.
    if (m.type !== MSG_TO_PREVIEW || Date.now() < snapUntil) return;
    ignoreUntil = Date.now() + ECHO_GUARD_MS;
    el().scrollTop = m.ratio * maxScroll();
  });

  window.addEventListener(
    "scroll",
    function () {
      if (Date.now() < ignoreUntil) return;
      var max = maxScroll();
      parent.postMessage({ type: MSG_FROM_PREVIEW, ratio: max ? el().scrollTop / max : 0 }, "*");
    },
    { passive: true },
  );

  parent.postMessage({ type: MSG_PREVIEW_READY }, "*");
})();
