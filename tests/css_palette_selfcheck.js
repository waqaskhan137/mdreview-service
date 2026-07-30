#!/usr/bin/env node
// css_palette_selfcheck.js — the rev-3 token contract, mechanically enforced (#277).
//
// WHY. The Polish design (rev 3) is a theme specification with one binding rule: identical DOM in
// both themes, only token values change, and no component declares a colour literal. A rule like
// that survives exactly as long as something fails the build when it is broken. This file is that
// something. It guards four things:
//
//   a. CONTRACT VALUES — every contract token is declared exactly ONCE in theme.css, on :root,
//      as light-dark(light, dark) carrying exactly the contract's pair (#285 single-source; a
//      token whose two sides are equal is a plain value). Theme arrival is color-scheme only:
//      :root says `light dark` (auto follows the OS), [data-theme="light"|"dark"] pin it. The one
//      non-colour dark delta (font-weight 350) is the ONLY declaration allowed to ship via the
//      two arrival selectors; the media block may contain nothing else, so the retired duplicated
//      dark table cannot creep back. Each dark literal appears exactly once in the file (#285
//      AC 7's grep half).
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

// The scopes of the #285 structure. Structure assertions are loud on purpose: if the file is
// reorganised, this parser must be re-pointed, not silently matched against nothing.
const mLight = theme.match(/:root\{([^}]*)\}/);
const mExplicitLight = theme.match(/:root\[data-theme="light"\]\s*\{([^}]*)\}/);
const mExplicitDark = theme.match(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/);
const mMediaDark = theme.match(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{([^}]*)\}/);
const mMobile = theme.match(/@media\s*\(max-width:\s*767px\)\s*\{\s*:root\s*\{([^}]*)\}/);
check("theme.css has the base :root, both data-theme overrides, the media dark-delta block and the mobile type block",
  !!(mLight && mExplicitLight && mExplicitDark && mMediaDark && mMobile),
  "missing: " + [["base :root", mLight], ["explicit light", mExplicitLight],
                 ["explicit dark", mExplicitDark], ["media dark delta", mMediaDark],
                 ["mobile type", mMobile]]
                .filter((p) => !p[1]).map((p) => p[0]).join(", "));

// The expected single-source declaration for a [light, dark] contract pair: the value itself when
// both sides agree, light-dark(l, d) for a plain colour, and for a shadow the shared geometry
// with light-dark() on the colour part (light-dark() is a <color>, it cannot wrap the geometry).
function expectedDecl(tok, lv, dv) {
  const l = norm(lv), d = norm(dv);
  if (l === d) return l;
  const colour = /(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/;
  const lc = l.match(colour), dc = d.match(colour);
  if (!lc || !dc) return null; // no colour tail — light-dark() cannot express this pair
  const lPre = l.slice(0, lc.index), dPre = d.slice(0, dc.index);
  if (lPre !== dPre) return null; // geometry differs between themes — not single-sourceable
  return lPre + "light-dark(" + lc[0] + ", " + dc[0] + ")";
}

if (mLight && mExplicitLight && mExplicitDark && mMediaDark && mMobile) {
  const light = decls(mLight[1]);
  const exLight = decls(mExplicitLight[1]);
  const exDark = decls(mExplicitDark[1]);
  const mediaDark = decls(mMediaDark[1]);
  const mobile = decls(mMobile[1]);

  // a1. Every contract token: exactly one declaration in the whole file, on :root, carrying the
  //     contract pair as a single light-dark() source.
  const bad = [];
  for (const [tok, [lv, dv]] of Object.entries(CONTRACT)) {
    const want = expectedDecl(tok, lv, dv);
    if (want === null) { bad.push(tok + ": the contract pair cannot be expressed as one light-dark() declaration"); continue; }
    const n = (theme.match(new RegExp("(^|[^-\\w])" + tok + "\\s*:", "g")) || []).length;
    if (n !== 1) bad.push(tok + " declared " + n + "x in theme.css, single-source says exactly 1");
    if (!(tok in light)) bad.push(tok + " missing from the base :root");
    else if (light[tok] !== norm(want)) bad.push(tok + " is '" + light[tok] + "', contract says '" + want + "'");
  }
  check("every contract token is declared once, on :root, with the contract's light-dark pair",
    bad.length === 0, bad.join(" | "));

  // a2. Each dark literal appears exactly once in the file (#285 AC 7): scan every light-dark()
  //     call (balanced-paren, since rgba() nests commas) and count its dark argument's
  //     occurrences. Covers legacy pairs too, mechanically.
  const darkLits = [];
  for (let at = theme.indexOf("light-dark("); at !== -1; at = theme.indexOf("light-dark(", at + 1)) {
    let depth = 1, args = [""], j = at + "light-dark(".length;
    for (; j < theme.length && depth > 0; j++) {
      const ch = theme[j];
      if (ch === "(") depth++;
      else if (ch === ")") { depth--; if (depth === 0) break; }
      if (depth === 1 && ch === ",") args.push("");
      else args[args.length - 1] += ch;
    }
    if (args.length === 2) darkLits.push(norm(args[1]));
  }
  const dup = [];
  check("theme.css carries light-dark() pairs to scan", darkLits.length > 0,
    "no light-dark() found — the single-source structure is gone");
  for (const darkLit of new Set(darkLits)) {
    const esc = darkLit.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const n = (norm(theme).match(new RegExp(esc, "g")) || []).length;
    if (n !== 1) dup.push(darkLit + " appears " + n + "x (a second copy is the old duplicated table creeping back)");
  }
  check("each dark colour literal appears exactly once in theme.css", dup.length === 0, dup.join(" | "));

  // a3. Theme arrival is color-scheme: auto on :root, pinned by the two overrides. The explicit
  //     blocks stay MINIMAL — colour may never be redeclared there.
  const arr = [];
  if (light["color-scheme"] !== "light dark") arr.push(":root color-scheme is '" + light["color-scheme"] + "', auto needs 'light dark'");
  if (exLight["color-scheme"] !== "light") arr.push('[data-theme="light"] color-scheme is \'' + exLight["color-scheme"] + "'");
  if (exDark["color-scheme"] !== "dark") arr.push('[data-theme="dark"] color-scheme is \'' + exDark["color-scheme"] + "'");
  for (const [scope, map, allowed] of [["explicit-light", exLight, ["color-scheme"]],
                                       ["explicit-dark", exDark, ["color-scheme", "font-weight"]],
                                       ["media dark-delta", mediaDark, ["font-weight"]]]) {
    const extra = Object.keys(map).filter((k) => !allowed.includes(k));
    if (extra.length) arr.push(scope + " block declares more than " + allowed.join("+") + ": " + extra.join(", "));
  }
  check("theme arrival is color-scheme-only (overrides are flips, not tables)",
    arr.length === 0, arr.join(" | "));

  // a4. Dark body weight 350 arrives from the theme via BOTH arrival paths — the one legal
  //     non-colour duplication (light-dark() only takes <color>; needs the variable Geist file).
  check("both dark arrival selectors set font-weight 350",
    mediaDark["font-weight"] === "350" && exDark["font-weight"] === "350",
    "rev 3: dark body weight drops 400 -> 350 from the theme, not per element");

  // a5. Type scale, desktop and the mobile floor.
  const tbad = [];
  for (const [tok, want] of Object.entries(TYPE_ROOT))
    if (light[tok] !== want) tbad.push(tok + " is '" + light[tok] + "', rev 3 says '" + want + "'");
  for (const [tok, want] of Object.entries(TYPE_MOBILE))
    if (mobile[tok] !== want) tbad.push("mobile " + tok + " is '" + mobile[tok] + "', rev 3 says '" + want + "'");
  check("type scale matches rev 3 (desktop + mobile floor)", tbad.length === 0, tbad.join(" | "));

  // a6. Legacy tokens still defined while their consumers live.
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
  // dashboard.html: EMPTY since #278 — the sign-in logo gradient (its last three literals) now
  // renders from --accent/--bg, per the rev-3 mock.

  // viewer.html: EMPTY since #279 (the re-skin replaced every literal with a contract token,
  // including the 3x #5b46e6 drift defect — an off-palette accent where the accent is #5B30D6).
  // Any literal appearing in viewer.html again is a new violation, not a grandfathered one.

  // latex-viewer.html: EMPTY since #280 re-skinned it to the token contract (including the 3x
  // #5b46e6 drift defect, replaced with var(--accent)). New literals here have no exemption.

  // account.js injected styles (#281 re-skins account)
  { file: "static/account.js", literal: "#2f8f5b", count: 1, ticket: "#281" },
  { file: "static/account.js", literal: "#9aa0a6", count: 1, ticket: "#281" },
  { file: "static/account.js", literal: "#fff", count: 1, ticket: "#281" },
  { file: "static/account.js", literal: "rgba(0,0,0,.12)", count: 1, ticket: "#281" },

  // static/keys.js: EMPTY since #285 re-pointed the keysheet at the contract tokens. The old
  // var() fallbacks existed for pages without the tokens; since #277 every page links theme.css,
  // and those literal fallbacks were where the dark-keycap bug lived. New literals here have no
  // exemption.
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
