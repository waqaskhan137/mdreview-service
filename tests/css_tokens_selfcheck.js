#!/usr/bin/env node
// css_tokens_selfcheck.js — every design token a page uses must actually exist (#261).
//
// WHY. #183 shipped `.cmdrow[aria-selected="true"]{background:var(--accent-soft)}`. There is no
// `--accent-soft`. It appeared exactly once in the repo — in that line, as its own consumer — so
// the keyboard-selected row in the ⌘K palette rendered fully transparent, identical to an
// unselected row, and arrow-key navigation produced no visible change whatsoever.
//
// Nothing caught it. Not the unit checks, not the mutation tests, not review. An undefined CSS
// custom property is not an error: the declaration is simply dropped, silently, and the element
// keeps whatever it had. That is the entire failure mode this file exists for.
//
// A token used with a fallback -- var(--x, something) -- is fine by design and is skipped: the
// fallback IS the definition for that use.
//
//   node tests/css_tokens_selfcheck.js     # exit 0 = pass

const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const APP = path.join(ROOT, "web", "app");

// Definitions come from the theme plus each file's own :root/inline declarations.
const theme = fs.readFileSync(path.join(APP, "static", "theme.css"), "utf8");
const defined = new Set([...theme.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((m) => m[1]));
// Basecoat ships its own token layer (--radius-lg, --color-*). Pages that LINK it may use them;
// the two viewers deliberately do not link it, so for those the same token would be undefined.
const bcPath = path.join(APP, "static", "basecoat.cdn.min.css");
const bcTokens = fs.existsSync(bcPath)
  ? new Set([...fs.readFileSync(bcPath, "utf8").matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((m) => m[1]))
  : new Set();

const FILES = ["dashboard.html", "viewer.html", "latex-viewer.html", "account.html", "admin.html"]
  .map((f) => path.join(APP, f))
  .filter(fs.existsSync)
  .concat([path.join(APP, "static", "account.js")].filter(fs.existsSync));

let failed = 0;
const check = (name, cond, why) => {
  console.log((cond ? "ok   - " : "FAIL - ") + name + (!cond && why ? "  <- " + why : ""));
  if (!cond) failed++;
};

for (const file of FILES) {
  const src = fs.readFileSync(file, "utf8");
  const rel = path.relative(ROOT, file);
  // This file's own declarations count as defined for itself.
  const local = new Set([...src.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((m) => m[1]));
  // A page that links Basecoat may use Basecoat's tokens; one that does not, may not.
  const usesBasecoat = /basecoat\.cdn\.min\.css/.test(src) || /basecoat-theme\.css/.test(src);
  // Bare var(--x), i.e. no fallback of its own. Uses sitting IN another var's fallback slot are
  // skipped: `var(--a, var(--b))` already degrades safely, and flagging --b would report a
  // last-resort as if it were a live dependency.
  const stripped = src.replace(/var\(\s*--[a-z0-9-]+\s*,[^)]*\)/gi, "");
  const bare = [...stripped.matchAll(/var\(\s*(--[a-z0-9-]+)\s*\)/gi)].map((m) => m[1]);
  const undef = [...new Set(bare)].filter(
    (t) => !defined.has(t) && !local.has(t) && !(usesBasecoat && bcTokens.has(t))
  );
  check(
    rel + ": every bare var(--token) is defined",
    undef.length === 0,
    undef.length ? "undefined: " + undef.join(", ") + " (the declaration is silently dropped)" : ""
  );
}

// The specific regression, named, so its return is unmistakable rather than one entry in a list.
const dash = fs.readFileSync(path.join(APP, "dashboard.html"), "utf8");
const code = dash.replace(/\/\*[\s\S]*?\*\//g, "");   // a comment naming the dead token is fine
check(
  "--accent-soft is gone from dashboard.html",
  !/var\(\s*--accent-soft/.test(code),
  "it never existed; the palette's selected row was invisible in both themes"
);
check(
  "the selected palette row uses a defined token",
  /\.cmdrow\[aria-selected="true"\]\{[^}]*var\(--accent-muted\)/.test(code),
  "--accent-muted is the real token (#F1ECFA light / #2A2540 dark); #277 renamed it from --accent-bg"
);
check(
  "selection carries a non-colour signal too",
  /\.cmdrow\[aria-selected="true"\]::before/.test(code),
  "hover and selection are otherwise two tints of one idea, and a hovering mouse hides the keyboard cursor"
);

console.log(failed ? "\n" + failed + " case(s) failed" : "\nall css-token cases pass");
process.exit(failed ? 1 : 0);
