// preview-sync.mjs
// Scroll sync between the Monaco editor and the sandboxed preview iframe.
//
// The preview iframe has no same-origin access, so the two sides talk through
// postMessage. A small script injected into the preview HTML handles the
// iframe side. Plain .mjs (not .ts) so the Node test suite can import it.

export const MSG_TO_PREVIEW = "mdr-scroll";
export const MSG_FROM_PREVIEW = "mdr-preview-scroll";
export const MSG_PREVIEW_READY = "mdr-preview-ready";
export const MSG_SNAP = "mdr-snap";
// After one side scrolls the other, ignore the echo for this long.
export const ECHO_GUARD_MS = 150;
// Long enough to cover the preview's smooth-scroll animation.
export const SNAP_GUARD_MS = 900;

const HEADING_RE = /^#{1,6}\s/;
const FENCE_RE = /^\s*(```|~~~)/;

/**
 * Locate a source line relative to the Markdown headings around it.
 * Returns the index of the last heading at or above the line (-1 if none) and
 * how far the line sits between that heading and the next one (0..1).
 * Headings inside fenced code blocks are ignored, matching the rendered HTML.
 *
 * @param {string[]} lines document lines
 * @param {number} lineNumber 1-based line number
 * @returns {{ heading: number, fraction: number }}
 */
export function locateLine(lines, lineNumber) {
  const headingLines = [];
  let inFence = false;
  lines.forEach((text, i) => {
    if (FENCE_RE.test(text)) inFence = !inFence;
    else if (!inFence && HEADING_RE.test(text)) headingLines.push(i + 1);
  });
  let heading = -1;
  while (heading + 1 < headingLines.length && headingLines[heading + 1] <= lineNumber) heading++;
  const start = heading >= 0 ? headingLines[heading] : 1;
  const end = headingLines[heading + 1] ?? lines.length + 1;
  const fraction = end > start ? Math.min(1, Math.max(0, (lineNumber - start) / (end - start))) : 0;
  return { heading, fraction };
}

/** Script that runs inside the preview iframe. */
export const SYNC_SCRIPT = `<script>(function(){
var ignoreUntil=0,snapUntil=0;
function el(){return document.scrollingElement||document.documentElement;}
function maxScroll(){return Math.max(0,el().scrollHeight-window.innerHeight);}
function pageTop(n){return n.getBoundingClientRect().top+el().scrollTop;}
function snap(m){
  var hs=document.body.querySelectorAll("h1,h2,h3,h4,h5,h6");
  var docEnd=el().scrollHeight;
  var start=m.heading>=0&&hs[m.heading]?pageTop(hs[m.heading]):0;
  var next=hs[m.heading+1]?pageTop(hs[m.heading+1]):docEnd;
  var y=start+m.fraction*Math.max(0,next-start);
  var blocks=document.body.querySelectorAll("h1,h2,h3,h4,h5,h6,p,li,pre,blockquote,table,img,hr");
  var target=null,best=Infinity;
  for(var i=0;i<blocks.length;i++){var d=Math.abs(pageTop(blocks[i])-y);if(d<best){best=d;target=blocks[i];}}
  if(target)y=pageTop(target);
  ignoreUntil=snapUntil=Date.now()+${SNAP_GUARD_MS};
  window.scrollTo({top:Math.max(0,y-window.innerHeight*0.3),behavior:"smooth"});
  if(target){
    var prev=target.style.backgroundColor,prevT=target.style.transition;
    target.style.transition="background-color 0.6s ease";
    target.style.backgroundColor="rgba(59,130,246,0.22)";
    setTimeout(function(){target.style.backgroundColor=prev;setTimeout(function(){target.style.transition=prevT;},600);},500);
  }
}
window.addEventListener("message",function(e){
  if(e.source!==parent)return;
  var m=e.data;
  if(!m)return;
  if(m.type==="${MSG_SNAP}"){snap(m);return;}
  // A click can nudge the editor's scroll; don't let that cancel the glide.
  if(m.type!=="${MSG_TO_PREVIEW}"||Date.now()<snapUntil)return;
  ignoreUntil=Date.now()+${ECHO_GUARD_MS};
  el().scrollTop=m.ratio*maxScroll();
});
window.addEventListener("scroll",function(){
  if(Date.now()<ignoreUntil)return;
  var max=maxScroll();
  parent.postMessage({type:"${MSG_FROM_PREVIEW}",ratio:max?el().scrollTop/max:0},"*");
},{passive:true});
parent.postMessage({type:"${MSG_PREVIEW_READY}"},"*");
})();</script>`;

/**
 * Insert the sync script into preview HTML, before </body> when present.
 * @param {string} html
 * @returns {string}
 */
export function withSyncScript(html) {
  const closeBody = html.lastIndexOf("</body>");
  if (closeBody === -1) return html + SYNC_SCRIPT;
  return html.slice(0, closeBody) + SYNC_SCRIPT + html.slice(closeBody);
}

/**
 * Scroll position as a 0..1 fraction of the scrollable range.
 * @param {number} scrollTop
 * @param {number} scrollHeight
 * @param {number} viewportHeight
 */
export function scrollRatio(scrollTop, scrollHeight, viewportHeight) {
  const max = scrollHeight - viewportHeight;
  return max > 0 ? Math.min(1, Math.max(0, scrollTop / max)) : 0;
}
