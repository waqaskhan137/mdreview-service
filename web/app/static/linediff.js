/* Shared line diff for the viewers (#19 lineDiff, #207 hunking).
 *
 * Both viewers need this: viewer.html renders it in place of the reading column, latex-viewer.html
 * in place of the source pane (#208). It lives here rather than inline in either page so there is
 * exactly ONE implementation — two copies would drift, and the drift would be silent because a
 * diff that is subtly wrong still looks like a diff.
 *
 * Self-hosted, no build step, no dependency: a plain script tag defines window.mdDiff. The
 * module.exports tail at the bottom is what lets tests/diff_selfcheck.js require() this file
 * directly instead of scraping the function out of the HTML, which is how the no-drift property is
 * now enforced structurally rather than by comment.
 */
(function (root) {
  "use strict";

  /* Rendering constants, taken from VS Code's diff editor rather than invented. Its defaults are
   * diffEditor.hideUnchangedRegions.{contextLineCount,minimumLineCount,revealLineCount}; matching
   * them means the collapse behaviour is already familiar to anyone who reads diffs in an editor.
   *   CONTEXT  lines kept either side of a change.
   *   MIN_GAP  a run of unchanged lines shorter than this is NOT collapsed: hiding two lines behind
   *            a click costs the reader more than the two lines it saves.
   *   REVEAL   lines revealed per expand, so opening a fold in a long document never dumps the
   *            whole file back into view. */
  var CONTEXT = 3, MIN_GAP = 3, REVEAL = 20;

  /* Pure LCS line diff — moved VERBATIM from viewer.html (#19), no behaviour change. Returns one
   * row per line: {tag:' '|'+'|'-', text}. No DOM, no globals, so it stays unit-testable. */
  function lineDiff(aText, bText) {
    var a = String(aText).split('\n'), b = String(bText).split('\n');
    var n = a.length, m = b.length;
    var dp = [];                                 // dp[i][j] = LCS length of a[i:] vs b[j:]
    for (var i0 = 0; i0 <= n; i0++) dp.push(new Int32Array(m + 1));
    for (var i1 = n - 1; i1 >= 0; i1--) for (var j1 = m - 1; j1 >= 0; j1--)
      dp[i1][j1] = a[i1] === b[j1] ? dp[i1 + 1][j1 + 1] + 1 : Math.max(dp[i1 + 1][j1], dp[i1][j1 + 1]);
    var out = [], i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { out.push({ tag: ' ', text: a[i] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ tag: '-', text: a[i] }); i++; }
      else { out.push({ tag: '+', text: b[j] }); j++; }
    }
    while (i < n) out.push({ tag: '-', text: a[i++] });
    while (j < m) out.push({ tag: '+', text: b[j++] });
    return out;
  }

  /* Attach old/new line numbers. A unified gutter needs both: a removed line has no new number and
   * an added line has no old one, which is exactly what tells the reader which side they are on. */
  function numberRows(rows) {
    var oa = 0, ob = 0;
    return rows.map(function (r) {
      if (r.tag === '-') { oa++; return { tag: r.tag, text: r.text, a: oa, b: null }; }
      if (r.tag === '+') { ob++; return { tag: r.tag, text: r.text, a: null, b: ob }; }
      oa++; ob++; return { tag: ' ', text: r.text, a: oa, b: ob };
    });
  }

  /* Group rows into alternating visible runs and collapsible gaps.
   *
   * Returns [{vis:true, rows:[…]}, {vis:false, rows:[…]}, …]. Callers render a visible segment as
   * plain rows and a hidden one as a fold. This is the piece that did not exist: renderDiff used to
   * print every row, so a 400-line document with a two-line edit rendered 400 rows. */
  function hunkify(rows, opts) {
    opts = opts || {};
    var context = opts.context == null ? CONTEXT : opts.context;
    var minGap = opts.minGap == null ? MIN_GAP : opts.minGap;

    var keep = new Array(rows.length);
    for (var k = 0; k < rows.length; k++) keep[k] = false;
    rows.forEach(function (r, idx) {
      if (r.tag === ' ') return;
      var lo = Math.max(0, idx - context), hi = Math.min(rows.length - 1, idx + context);
      for (var c = lo; c <= hi; c++) keep[c] = true;
    });

    var segs = [], i = 0;
    while (i < rows.length) {
      var start = i, vis = keep[i];
      while (i < rows.length && keep[i] === vis) i++;
      var slice = rows.slice(start, i);
      // Promote a too-short gap back to visible, then merge it into the run before it so callers
      // never see two adjacent visible segments (which would render as a seam that isn't there).
      if (!vis && slice.length < minGap) vis = true;
      var last = segs[segs.length - 1];
      if (last && last.vis && vis) last.rows = last.rows.concat(slice);
      else segs.push({ vis: vis, rows: slice });
    }
    return segs;
  }

  /* Convenience for the callers: counts for the toggle's hint badge. */
  function counts(rows) {
    var add = 0, del = 0;
    rows.forEach(function (r) { if (r.tag === '+') add++; else if (r.tag === '-') del++; });
    return { add: add, del: del, changed: add + del };
  }

  var api = {
    lineDiff: lineDiff, numberRows: numberRows, hunkify: hunkify, counts: counts,
    CONTEXT: CONTEXT, MIN_GAP: MIN_GAP, REVEAL: REVEAL
  };

  root.mdDiff = api;
  // Node (tests/diff_selfcheck.js) — ignored by browsers, so the same file serves both.
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : this);
