#!/usr/bin/env node
// css_palette_selfcheck.js — the rev-3 token contract, mechanically enforced (#277).
//
// WHY. The Polish design (rev 3) is a theme specification with one binding rule: identical DOM in
// both themes, only token values change, and no component declares a colour literal. A rule like
// that survives exactly as long as something fails the build when it is broken. This file is that
// something. It guards four things:
//
//   a. CONTRACT VALUES — every contract token is defined in all three scopes of theme.css
//      (light :root, the media dark block, the explicit [data-theme="dark"] block) with exactly
//      the contract's values, and the two dark blocks are value-identical. The dark table exists
//      twice on purpose (two arrival paths for one theme); duplication is a drift hazard only if
//      nothing asserts identity, so this asserts identity.
//   b. NO LITERALS — no colour literal (#hex / rgb() / rgba() / hsl() / hsla()) in first-party
//      style sources outside theme.css's token definitions.
//   c. ALLOWLIST — the pre-existing literals ship as an exact, counted, ticket-tagged list below.
//      Emptying it is epic #276's exit criterion, owned by the re-skin tickets, not by weakening
//      this file. A literal above its count fails (someone snuck a new copy in behind an existing
//      exemption); below its count fails too (the entry is stale: shrink the list in the same
//      change that removed the literal, so the list always states the truth).
//   d. FONTS — every @font-face src in theme.css is a same-directory url() whose file exists, and
//      the Google Fonts CDN appears nowhere under web/app. Self-hosted is a design decision, not
//      a default.
//
// This is a STATIC check of the source. It cannot prove the rendered outcome (the #265 lesson:
// a CSS-text assertion sat green for two days over a broken layout); computed-style verification
// in a real browser is the AC-4 evidence on the PR, not this file's job.
//
//   node tests/css_palette_selfcheck.js     # exit 0 = pass

const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const APP = path.join(ROOT, "web", "app");
const STATIC = path.join(APP, "static");

let failed = 0;
const check = (name, cond, why) => {
  console.log((cond ? "ok   - " : "FAIL - ") + name + (!cond && why ? "  <- " + why : ""));
  if (!cond) failed++;
};

/* ---------------------------------------------------------------------------------------------
 * a. The contract. Values are rev 3 of the Polish canvas, verbatim. If the design revs, this
 *    table revs with it in the same change; nothing else in the repo may restate these numbers.
 * ------------------------------------------------------------------------------------------- */
const CONTRACT = {
  //  token                light                                          dark
  "--bg":              ["#FCFBF9", "#14130F"],
  "--surface":         ["#FAF9F7", "#1F1D19"],
  "--surface-raised":  ["#FFFFFF", "#26231D"],
  "--text":            ["#1F1D1A", "#E8E4DC"],
  "--text-muted":      ["#57534B", "#9A948A"],
  "--text-subtle":     ["#6B6660", "#8F897F"],
  "--border":          ["#E6E2DC", "#2E2B26"],
  "--border-faint":    ["#EFECE6", "#232019"],
  "--accent":          ["#5B30D6", "#B5A7E6"],
  "--accent-strong":   ["#4423B0", "#C9BEEE"],
  "--accent-muted":    ["#F1ECFA", "#2A2540"],
  "--success":         ["#1F7A49", "#6DD39B"],
  "--success-bg":      ["#E6F4EC", "#1C2C22"],
  "--success-border":  ["#B7E0C8", "#2F4A39"],
  "--warning":         ["#8A6100", "#D0A24A"],
  "--warning-bg":      ["#F7EFDC", "#2B2317"],
  "--danger":          ["#C0392B", "#E07A7A"],
  "--danger-bg":       ["#FDECEA", "#33231D"],
  "--danger-border":   ["#E8C6BF", "#4A2F28"],
  "--code-bg":         ["#F4F2EE", "#24211C"],
  "--canvas":          ["#EAE7E0", "#100F0C"],
  "--paper":           ["#FFFFFF", "#FFFFFF"],
  "--paper-ink":       ["#1F1D1A", "#1F1D1A"],
  "--paper-ink-muted": ["#57534B", "#57534B"],
  "--scrim":           ["rgba(20,19,15,.42)", "rgba(0,0,0,.72)"],
  "--shadow-menu":     ["0 18px 44px -18px rgba(20,20,40,.35)", "0 18px 44px -18px rgba(0,0,0,.6)"],
  "--shadow-dock":     ["0 18px 40px -18px rgba(20,20,40,.28)", "0 18px 40px -18px rgba(0,0,0,.7)"],
  "--shadow-paper":    ["0 10px 30px -12px rgba(20,20,40,.3)", "0 10px 30px -12px rgba(0,0,0,.55)"],
  "--shadow-hair":     ["0 1px 0 rgba(20,20,40,.06)", "0 1px 0 rgba(0,0,0,.35)"],
};

// Rev-3 type scale (#277). Checked in :root and the mobile floor block.
const TYPE_ROOT = { "--t-title": "25px", "--t-card": "16px", "--t-body": "13px",
                    "--t-eyebrow": "12px", "--t-meta": "13px" };
const TYPE_MOBILE = { "--t-title": "24px", "--t-card": "17px", "--t-body": "16px" };

// Legacy tokens with no contract equivalent. They stay defined until the named tickets retire
// their consumers; deleting one early would silently drop declarations on live pages.
const LEGACY = { "--blue": "#278/#279", "--blue-bg": "#279", "--link": "#278",
                 "--nav-hover": "#278", "--nav-active": "#278" };

const stripCss = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "");
const norm = (v) => v.trim().replace(/\s+/g, " ").toLowerCase();
const decls = (block) => {
  const map = {};
  for (const d of block.split(";")) {
    const i = d.indexOf(":");
    if (i < 0) continue;
    const prop = d.slice(0, i).trim();
    if (!prop) continue;
    map[prop] = norm(d.slice(i + 1));
  }
  return map;
};

const themeRaw = fs.readFileSync(path.join(STATIC, "theme.css"), "utf8");
const theme = stripCss(themeRaw);

// The three scopes plus the mobile block. Structure assertions are loud on purpose: if the file
// is reorganised, this parser must be re-pointed, not silently matched against nothing.
const mLight = theme.match(/:root\{([^}]*)\}/);
const mMediaDark = theme.match(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{([^}]*)\}/);
const mExplicitDark = theme.match(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/);
const mMobile = theme.match(/@media\s*\(max-width:\s*767px\)\s*\{\s*:root\s*\{([^}]*)\}/);
check("theme.css has all three theme scopes plus the mobile type block",
  !!(mLight && mMediaDark && mExplicitDark && mMobile),
  "missing: " + [["light :root", mLight], ["media dark", mMediaDark],
                 ["explicit dark", mExplicitDark], ["mobile type", mMobile]]
                .filter((p) => !p[1]).map((p) => p[0]).join(", "));

if (mLight && mMediaDark && mExplicitDark && mMobile) {
  const light = decls(mLight[1]);
  const dark1 = decls(mMediaDark[1]);   // media-dark block
  const dark2 = decls(mExplicitDark[1]); // explicit-dark block
  const mobile = decls(mMobile[1]);

  // a1. Every contract token, exact value, all three scopes.
  const bad = [];
  for (const [tok, [lv, dv]] of Object.entries(CONTRACT)) {
    for (const [scope, map, want] of [["light :root", light, lv],
                                      ["media-dark block", dark1, dv],
                                      ["explicit-dark block", dark2, dv]]) {
      if (!(tok in map)) bad.push(tok + " missing from the " + scope);
      else if (map[tok] !== norm(want)) bad.push(tok + " in the " + scope + " is '" + map[tok] + "', contract says '" + want + "'");
    }
  }
  check("every contract token carries the contract value in all three scopes",
    bad.length === 0, bad.join(" | "));

  // a2. The two dark blocks are value-identical, every declaration, both directions.
  const div = [];
  for (const k of new Set([...Object.keys(dark1), ...Object.keys(dark2)])) {
    if (!(k in dark1)) div.push(k + " only in the explicit-dark block");
    else if (!(k in dark2)) div.push(k + " only in the media-dark block");
    else if (dark1[k] !== dark2[k])
      div.push(k + " diverged: media-dark '" + dark1[k] + "' vs explicit-dark '" + dark2[k] + "'");
  }
  check("the two dark blocks are value-identical (one theme, two arrival paths)",
    div.length === 0, div.join(" | "));

  // a3. Dark body weight 350 arrives from the theme, both paths (needs the variable Geist file).
  check("both dark blocks set font-weight 350",
    dark1["font-weight"] === "350" && dark2["font-weight"] === "350",
    "rev 3: dark body weight drops 400 -> 350 from the theme, not per element");

  // a4. Type scale, desktop and the mobile floor.
  const tbad = [];
  for (const [tok, want] of Object.entries(TYPE_ROOT))
    if (light[tok] !== want) tbad.push(tok + " is '" + light[tok] + "', rev 3 says '" + want + "'");
  for (const [tok, want] of Object.entries(TYPE_MOBILE))
    if (mobile[tok] !== want) tbad.push("mobile " + tok + " is '" + mobile[tok] + "', rev 3 says '" + want + "'");
  check("type scale matches rev 3 (desktop + mobile floor)", tbad.length === 0, tbad.join(" | "));

  // a5. Legacy tokens still defined while their consumers live.
  const lbad = Object.entries(LEGACY).filter(([t]) => !(t in light))
    .map(([t, owner]) => t + " (retired by " + owner + ", which has not landed)");
  check("legacy tokens survive until their re-skin tickets retire their consumers",
    lbad.length === 0, lbad.join(" | "));
}

/* ---------------------------------------------------------------------------------------------
 * b + c. The no-literal rule and its exact allowlist.
 *
 * An exception is legal ONLY as an entry here: file + exact literal + occurrence count + owning
 * ticket. These are the literals measured on this tree when #277 landed; every one predates the
 * contract. The re-skin tickets remove them AND their entries in the same change.
 * ------------------------------------------------------------------------------------------- */
const ALLOWLIST = [
  // dashboard.html — the avatar gradient (#278 re-skins the dashboard)
  { file: "dashboard.html", literal: "#2f6fed", count: 1, ticket: "#278" },
  { file: "dashboard.html", literal: "#7c4dff", count: 1, ticket: "#278" },
  { file: "dashboard.html", literal: "#fff", count: 1, ticket: "#278" },

  // viewer.html (#279 re-skins the markdown viewer).
  // NOTE the 3x #5b46e6: a live drift defect, an off-palette accent where the accent is #5B30D6.
  // This list documents it; #279 fixes it. It is exactly the class of bug this file exists to
  // make impossible to reintroduce.
  { file: "viewer.html", literal: "#5b46e6", count: 3, ticket: "#279" },
  { file: "viewer.html", literal: "#c0392b", count: 4, ticket: "#279" },
  { file: "viewer.html", literal: "#fafaf9", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "#fff", count: 7, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.06)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.18)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.2)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.25)", count: 4, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.3)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.45)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.5)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(0,0,0,.85)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(20,22,40,.16)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(29,79,191,.08)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(91,48,214,.06)", count: 2, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(91,48,214,.07)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(91,48,214,.18)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(91,48,214,.40)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(127,127,127,.04)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(127,127,127,.05)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(127,127,127,.06)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(127,127,127,.1)", count: 2, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(127,127,127,.12)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(127,127,127,.16)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(192,57,43,.1)", count: 1, ticket: "#279" },
  { file: "viewer.html", literal: "rgba(192,57,43,.10)", count: 1, ticket: "#279" },

  // latex-viewer.html: EMPTY since #280 re-skinned it to the token contract (including the 3x
  // #5b46e6 drift defect, replaced with var(--accent)). New literals here have no exemption.

  // account.js injected styles (#281 re-skins account)
  { file: "static/account.js", literal: "#2f8f5b", count: 1, ticket: "#281" },
  { file: "static/account.js", literal: "#9aa0a6", count: 1, ticket: "#281" },
  { file: "static/account.js", literal: "#fff", count: 1, ticket: "#281" },
  { file: "static/account.js", literal: "rgba(0,0,0,.12)", count: 1, ticket: "#281" },

  // keys.js ⌘K/help-sheet styles. No live ticket owns its re-skin; tagged to epic #276 until one
  // does. These are var() fallbacks by design (the sheet renders on pages without the tokens).
  { file: "static/keys.js", literal: "#111", count: 2, ticket: "#276" },
  { file: "static/keys.js", literal: "#16161a", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#24242a", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#2c2c33", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#3a3a42", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#d7d7de", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#e3e3e8", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#eee", count: 2, ticket: "#276" },
  { file: "static/keys.js", literal: "#f6f6f8", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "#fff", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "rgba(0,0,0,.25)", count: 1, ticket: "#276" },
  { file: "static/keys.js", literal: "rgba(0,0,0,.45)", count: 1, ticket: "#276" },
];

// First-party style sources. Vendored bundles are excluded by name, never by pattern-weakening:
// their palettes are not ours to police.
const FIRST_PARTY = ["dashboard.html", "viewer.html", "latex-viewer.html", "account.html",
  "admin.html", "static/account.js", "static/keys.js", "static/basecoat-theme.css"];
const VENDORED = ["basecoat.cdn.min.css", "katex.min.css", "hljs-github.css",
  "basecoat.all.min.js", "highlight.min.js"];

// Comment stripping. Issue refs in comments (#183, #309) parse as 3-digit hex, the same false
// positive css_tokens_selfcheck.js already strips comments for. JS line comments are stripped
// only when // follows start-of-line or whitespace, so protocol URLs survive.
function stripComments(src, file) {
  let s = src.replace(/\/\*[\s\S]*?\*\//g, "");
  if (/\.html$/.test(file)) s = s.replace(/<!--[\s\S]*?-->/g, "");
  if (/\.js$/.test(file) || /\.html$/.test(file)) s = s.replace(/(^|\s)\/\/[^\n]*/g, "$1");
  return s;
}

const LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)/g;
const isHexLen = (m) => !m.startsWith("#") || [3, 4, 6, 8].includes(m.length - 1);

function literalsIn(text) {
  const found = {};
  for (const m of text.match(LITERAL) || []) {
    if (!isHexLen(m)) continue;
    const key = m.startsWith("#") ? m.toLowerCase() : m;
    found[key] = (found[key] || 0) + 1;
  }
  return found;
}

for (const rel of FIRST_PARTY) {
  const file = path.join(APP, rel);
  const found = literalsIn(stripComments(fs.readFileSync(file, "utf8"), rel));
  const allowed = ALLOWLIST.filter((e) => e.file === rel);
  const problems = [];
  for (const [lit, n] of Object.entries(found)) {
    const entry = allowed.find((e) => e.literal.toLowerCase() === lit.toLowerCase());
    if (!entry) problems.push("unlisted literal " + lit + " (x" + n + ")");
    else if (n > entry.count) problems.push(lit + " appears " + n + "x, allowlist says " + entry.count + "x (" + entry.ticket + " owns the old ones; the new one has no ticket)");
    else if (n < entry.count) problems.push(lit + " appears " + n + "x, allowlist says " + entry.count + "x (stale entry: shrink it in the change that removed the literal)");
  }
  for (const e of allowed)
    if (!(e.literal.toLowerCase() in Object.fromEntries(Object.entries(found).map(([k, v]) => [k.toLowerCase(), v]))))
      problems.push("stale allowlist entry: " + e.literal + " no longer occurs (remove it, " + e.ticket + ")");
  check("web/app/" + rel + ": no colour literal outside the allowlist",
    problems.length === 0, problems.join(" | "));
}

// theme.css itself: literals are legal ONLY inside custom-property (token) declarations. Rules
// below the token blocks must resolve through var() like everyone else.
{
  const noTokens = stripCss(themeRaw).replace(/--[a-zA-Z0-9-]+\s*:[^;}]*/g, "");
  const stray = Object.entries(literalsIn(noTokens)).map(([l, n]) => l + " (x" + n + ")");
  check("theme.css declares literals only in token definitions",
    stray.length === 0, stray.join(" | "));
}

// Vendored exclusion is by explicit name: fail loudly if a name drifts so the exclusion list
// cannot silently rot into excluding first-party files.
for (const v of ["basecoat.cdn.min.css"])
  check("vendored exclusion still names a real file: " + v,
    fs.existsSync(path.join(STATIC, v)), "the exclusion list in this file needs re-pointing");

/* ---------------------------------------------------------------------------------------------
 * d. Fonts: same-origin, same-directory, present on disk; the CDN appears nowhere.
 * ------------------------------------------------------------------------------------------- */
{
  const faces = [...stripCss(themeRaw).matchAll(/@font-face\s*\{([^}]*)\}/g)];
  check("theme.css declares @font-face rules", faces.length >= 4,
    "expected the four vendored variable fonts, found " + faces.length);
  const fbad = [];
  for (const f of faces) {
    const src = (f[1].match(/src\s*:\s*url\(\s*["']?([^"')]+)["']?\s*\)/) || [])[1];
    if (!src) { fbad.push("a @font-face has no url() src"); continue; }
    if (/:\/\//.test(src) || src.startsWith("/") || src.includes(".."))
      fbad.push(src + " is not a same-directory URL");
    else if (!fs.existsSync(path.join(STATIC, src)))
      fbad.push(src + " is declared but the file does not exist in web/app/static/");
  }
  check("every @font-face src is a same-directory file that exists", fbad.length === 0,
    fbad.join(" | "));
}
{
  const hits = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) { walk(p); continue; }
      if (/\.(woff2|png|jpg|gif|ico)$/.test(e.name)) continue;
      const s = fs.readFileSync(p, "utf8");
      if (s.includes("fonts.googleapis") || s.includes("fonts.gstatic"))
        hits.push(path.relative(ROOT, p));
    }
  };
  walk(APP);
  check("fonts.googleapis / fonts.gstatic appear nowhere under web/app", hits.length === 0,
    "CDN reference in: " + hits.join(", ") + " (the fonts are vendored; a CDN link reintroduces the tracking + availability dependency the epic removed)");
}

console.log(failed ? "\n" + failed + " case(s) failed" : "\nall palette-contract cases pass");
process.exit(failed ? 1 : 0);
