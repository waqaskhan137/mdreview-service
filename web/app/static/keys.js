// keys.js (#222) — the one keyboard-shortcut dispatcher, shared by every page.
//
// Before this file the whole app had two ad-hoc key handlers: an Escape-closes-the-lightbox global
// in viewer.html and an Enter inside latex-viewer's line-number popup. No dispatch, no help sheet,
// no way to discover that anything was bound at all.
//
// A page calls register() with its own table and the shared ones are merged in. The help sheet is
// GENERATED from that table, so a binding cannot exist undocumented: adding a row to the table is
// the only way to add a shortcut, and it shows up in the sheet for free.
//
//   mdKeys.register([
//     { keys: "c", label: "Toggle comments", run: () => click("#cmtbtn") },
//   ]);
//
// Entry shape:
//   keys   a single key spec, or an array of them: "c", "?", "Escape", "mod+/", "mod+Enter", "1"
//   label  the human sentence shown in the help sheet. Required: no label, no binding.
//   run    (event) => void. Return false to indicate "I did nothing", which lets Escape fall
//          through to the next handler in the stack.
//   when   optional () => boolean guard. A binding whose guard is false is skipped AND hidden
//          from the sheet, so the sheet never advertises something inert.
//   keepInField  optional. By default a binding is suppressed while focus is in a text field,
//          because the comment composer would otherwise eat "c", "a" and "r". Only the help sheet
//          and the composer's own submit set this.
//
// TWO TRAPS, both load-bearing:
//   1. "/" and "?" are the SAME physical key. Branching on e.key === "/" alone makes the dashboard's
//      search-focus binding swallow the help sheet. Every spec is normalised through keyOf(), which
//      reads e.shiftKey, so "/" and "?" are distinct entries.
//   2. The sheet must be reachable WHILE TYPING. It is the one thing a user hits when they are lost,
//      and being lost includes being lost inside a textarea.

(function (root) {
  var registry = [];          // every registered binding, in registration order
  var escStack = [];          // Escape handlers, innermost last (see pushEscape)
  var sheetEl = null;
  var lastFocus = null;

  function isField(el) {
    if (!el) return false;
    if (el.isContentEditable) return true;
    var t = (el.tagName || "").toLowerCase();
    return t === "input" || t === "textarea" || t === "select";
  }

  // Canonical spec for an event: "mod+/" | "?" | "c" | "Escape". `mod` is Cmd on mac, Ctrl
  // elsewhere, so a single spec covers both platforms.
  function keyOf(e) {
    var k = e.key;
    if (k === " ") k = "Space";
    var mod = e.metaKey || e.ctrlKey;
    // Shift is normally already baked into e.key for printable characters, so a physical Shift+/
    // arrives as "?" and adding a "shift+" prefix would double-count it and never match.
    //
    // "Normally" is doing real work in that sentence. Some input paths deliver the UNSHIFTED
    // character with shiftKey set instead: observed on staging as {key:"/", code:"Slash",
    // shift:true}. That made "/" win, so Shift+/ focused the dashboard search box instead of
    // opening the help sheet — the exact collision this function exists to prevent.
    //
    // So normalise rather than trust: with Shift held, Slash means "?" whichever form arrives.
    // On a path that already reports "?" this is a no-op.
    if (e.shiftKey && k === "/") k = "?";
    return (mod ? "mod+" : "") + k;
  }

  function isMac() {
    return /Mac|iPhone|iPad/.test((root.navigator && root.navigator.platform) || "");
  }

  function prettify(spec) {
    return spec
      .replace("mod+", isMac() ? "⌘" : "Ctrl+")
      .replace("Escape", "Esc")
      .replace("Enter", "↵");
  }

  function register(entries) {
    (entries || []).forEach(function (entry) {
      var keys = Array.isArray(entry.keys) ? entry.keys : [entry.keys];
      if (!entry.label) throw new Error("keys.js: a binding without a label cannot be documented");
      registry.push({ keys: keys, label: entry.label, run: entry.run,
                      when: entry.when || null, keepInField: !!entry.keepInField });
    });
  }

  // Escape is layered. viewer.html has a lightbox, a comment popup, a share popover and a history
  // modal, each of which used to close itself. One owner has to close the TOPMOST open layer only,
  // or Escape from the history modal would also dismiss the lightbox underneath it.
  // A handler returns true if it consumed the key; false means "I was not open, try the next one".
  function pushEscape(fn) { escStack.push(fn); return fn; }

  function runEscape() {
    for (var i = escStack.length - 1; i >= 0; i--) {
      if (escStack[i]() === true) return true;
    }
    return false;
  }

  function visible() {
    return registry.filter(function (b) { return !b.when || b.when(); });
  }

  function buildSheet() {
    var rows = visible().map(function (b) {
      return '<tr><td class="k">' +
        b.keys.map(function (k) { return "<kbd>" + prettify(k) + "</kbd>"; }).join(" ") +
        '</td><td>' + b.label + "</td></tr>";
    }).join("");
    var el = document.createElement("div");
    el.id = "keysheet";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.setAttribute("aria-label", "Keyboard shortcuts");
    el.innerHTML = '<div class="keysheet-card"><div class="keysheet-head">' +
      "<strong>Keyboard shortcuts</strong>" +
      '<button type="button" class="keysheet-x" aria-label="Close">×</button></div>' +
      "<table>" + rows + "</table></div>";
    return el;
  }

  // Styles are injected rather than added to a stylesheet, for the same reason account.js does it:
  // the sheet appears on five pages and two of them (viewer, latex-viewer) are deliberately OFF
  // Basecoat, so there is no single stylesheet that reaches all of them. Colours resolve through
  // theme.css's contract tokens (#285): every page links theme.css, each token carries both
  // themes via light-dark(), and the tokens follow the EFFECTIVE theme — data-theme override
  // included — which is exactly what the old @media (prefers-color-scheme:dark) block here could
  // not do (it consulted the OS and disagreed with an explicit override; #285 deleted it). The
  // historical dark-keycap bug (kbd background restated without its COLOUR: unreadable keycaps
  // that still passed DOM assertions) cannot recur in this shape — kbd colour and background now
  // come from one token table. No literal fallbacks: theme.css is a hard dependency of every
  // page that loads this file. No Basecoat classes: `.dialog` is unavailable on the viewers.
  var CSS = "#keysheet{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;" +
    "justify-content:center;background:var(--scrim)}" +
    "#keysheet .keysheet-card{background:var(--surface-raised);color:var(--text);" +
    "border:1px solid var(--border);border-radius:var(--r-panel,10px);" +
    "min-width:min(420px,92vw);max-height:80vh;overflow:auto;padding:16px 18px;" +
    "box-shadow:var(--shadow-menu)}" +
    "#keysheet .keysheet-head{display:flex;align-items:center;justify-content:space-between;" +
    "gap:16px;margin-bottom:10px}" +
    "#keysheet .keysheet-x{background:none;border:0;font-size:20px;line-height:1;cursor:pointer;" +
    "color:inherit;padding:2px 6px}" +
    "#keysheet table{border-collapse:collapse;width:100%}" +
    "#keysheet td{padding:5px 0;vertical-align:top;font-size:14px}" +
    "#keysheet td.k{white-space:nowrap;padding-right:18px;width:1%}" +
    "#keysheet kbd{display:inline-block;border:1px solid var(--border);border-bottom-width:2px;" +
    "border-radius:5px;padding:1px 6px;font:inherit;font-size:12px;background:var(--code-bg);" +
    "color:var(--text)}";

  function injectCss() {
    if (document.getElementById("keysheet-css")) return;
    var s = document.createElement("style");
    s.id = "keysheet-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function openSheet() {
    if (sheetEl) return;
    injectCss();
    lastFocus = document.activeElement;
    sheetEl = buildSheet();
    document.body.appendChild(sheetEl);
    sheetEl.querySelector(".keysheet-x").addEventListener("click", closeSheet);
    sheetEl.addEventListener("click", function (e) { if (e.target === sheetEl) closeSheet(); });
    sheetEl.querySelector(".keysheet-x").focus();
  }

  function closeSheet() {
    if (!sheetEl) return;
    sheetEl.remove();
    sheetEl = null;
    // Put focus back where it was, or the user loses their place in the document they were reading.
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) { /* gone */ } }
    lastFocus = null;
  }

  function onKeydown(e) {
    if (e.defaultPrevented) return;
    var spec = keyOf(e);

    if (spec === "Escape") {
      if (sheetEl) { closeSheet(); e.preventDefault(); return; }
      if (runEscape()) e.preventDefault();
      return;
    }
    // The sheet is modal: while it is open, nothing else may fire.
    if (sheetEl) return;

    var inField = isField(e.target);
    for (var i = 0; i < registry.length; i++) {
      var b = registry[i];
      if (b.keys.indexOf(spec) < 0) continue;
      if (inField && !b.keepInField) continue;
      if (b.when && !b.when()) continue;
      if (b.run(e) !== false) e.preventDefault();
      return;
    }
  }

  // Click a control by selector. Bindings drive the REAL control rather than duplicating its
  // handler, so a shortcut cannot drift from what the button does.
  function click(sel) {
    var el = document.querySelector(sel);
    if (!el) return false;
    el.click();
    return true;
  }

  function focus(sel) {
    var el = document.querySelector(sel);
    if (!el) return false;
    el.focus();
    if (el.select) el.select();
    return true;
  }

  var api = {
    register: register, pushEscape: pushEscape, click: click, focus: focus,
    openSheet: openSheet, closeSheet: closeSheet,
    // exposed for tests/keys_selfcheck.js
    _keyOf: keyOf, _registry: registry, _visible: visible, _prettify: prettify, _isField: isField,
  };

  // The help sheet itself, registered first so it is the first row of every page's sheet.
  // keepInField: you look for help precisely when you are stuck, including mid-sentence.
  register([{ keys: ["mod+/", "?"], label: "Show this help", keepInField: true,
              run: function () { openSheet(); } }]);

  if (typeof document !== "undefined") {
    document.addEventListener("keydown", onKeydown);
  }

  root.mdKeys = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : this);
