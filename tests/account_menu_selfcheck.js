#!/usr/bin/env node
// account_menu_selfcheck.js — the shared account menu (#262).
//
// WHY THIS EXISTS. account.js mounts into #acct on FIVE pages (dashboard, viewer, latex-viewer,
// account, admin), so one bad branch ships everywhere at once. Its state machine has FOUR branches,
// not three — a grooming pass caught me asserting three, and a rewrite preserving three would have
// silently deleted the anonymous "Sign in" state.
//
// The branches, and what each is protecting against:
//   noAuthPlane   -> render NOTHING           (#224: a local build has no account to show)
//   !reachable    -> "Reconnecting…"          (#221: "could not ask" is not "signed out")
//   authenticated -> the menu
//   otherwise     -> "Sign in"                (a real signed-out visitor)
//
// Asserted against the SHIPPED file, because the failure mode is the file drifting from the
// contract, not a reconstruction of it drifting.
//
//   node tests/account_menu_selfcheck.js     # exit 0 = pass

const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const src = fs.readFileSync(path.join(ROOT, "web", "app", "static", "account.js"), "utf8");
// Colour assertions run against CODE, not prose: a comment that names a retired hex in order to
// say it is gone must not fail the check that it is gone. (Third time this run a check has fired
// on formatting rather than content — strip the thing you are not asserting about.)
const code = src.replace(/^\s*\/\/.*$/gm, "");
const theme = fs.readFileSync(path.join(ROOT, "web", "app", "static", "theme.css"), "utf8");

let failed = 0;
const check = (name, cond, why) => {
  console.log((cond ? "ok   - " : "FAIL - ") + name + (!cond && why ? "  <- " + why : ""));
  if (!cond) failed++;
};

// ---- 1. All four states survive. ----
check("noAuthPlane renders nothing", /noAuthPlane\)\s*\{\s*el\.innerHTML\s*=\s*""/.test(src),
      "a local build must not show a sign-in form that can never work (#224)");
check("unreachable renders Reconnecting, not a sign-in link", /Reconnecting/.test(src),
      "'could not ask' is not 'signed out' (#221)");
check("the anonymous state still offers Sign in", /acct-in[\s\S]{0,80}Sign in/.test(src),
      "THE state a 3-state rewrite would have deleted");
check("authenticated renders the menu", /acct-menu/.test(src));

// ---- 2. Menu contents and order. Sign out is last and separated. ----
const menuBlock = (src.match(/'<div class="acct-menu"[\s\S]*?"<\/div>";/) || [""])[0];
check("menu links to the account page", /href="\/account"/.test(menuBlock));
check("Sign out is present in the menu", /acct-out/.test(menuBlock));
const accIdx = menuBlock.indexOf('href="/account"');
const outIdx = menuBlock.indexOf("acct-out");
check("Sign out comes after navigation", accIdx > -1 && outIdx > accIdx,
      "the destructive-ish item must not sit above the navigation");
check("a separator divides navigation from Sign out", /acct-sep[\s\S]*acct-out/.test(menuBlock));

// ---- 3. Admin is conditional. This is the mutation target: force is_admin false. ----
check("Admin item is gated on sess.is_admin",
      /sess\.is_admin\s*\?\s*'<a class="acct-item" href="\/admin"/.test(src),
      "a non-admin must never be offered the admin console");

// ---- 4. Accessibility floor: a real button, real ARIA, real keyboard. ----
check("the trigger is a real <button>", /<button class="acct-trig" type="button"/.test(src));
check("the trigger declares aria-haspopup", /aria-haspopup="menu"/.test(src));
check("aria-expanded is maintained, not just set once",
      (src.match(/aria-expanded/g) || []).length >= 3,
      "it must flip on open AND close, so one occurrence means it is decorative");
check("Arrow keys move between items", /ArrowDown[\s\S]{0,400}ArrowUp/.test(src));
check("Escape closes the menu", /Escape[\s\S]{0,80}close\(true\)/.test(src));
check("Escape also routes through mdKeys where available",
      /mdKeys\.pushEscape/.test(src),
      "so the menu composes with the ? sheet and the palette instead of racing them");
check("a click outside closes it", /!el\.contains\(e\.target\)/.test(src));

// ---- 5. No hardcoded retired violet. The design doc retired #7c6cff; it was still here. ----
check("the retired #7c6cff is gone from account.js", !/7c6cff/i.test(code),
      "design-system-spec §01 retires it");
check("the admin colour is not a hardcoded hex",
      !/#6a5acd/i.test(code),
      "it must come from the token system, at a measured contrast");

// ---- 6. Motion lives in theme.css, NOT in the injected string. ----
// account.js appends its <style> AFTER theme.css's <link>, so an equal-specificity guard in
// theme.css cannot override a transition declared in the injected CSS. If the transition moves
// into account.js, the reduced-motion block silently stops working while still being present.
check("the menu transition is declared in theme.css", /\.acct-menu\{[^}]*transition/.test(theme));
check("account.js does NOT declare the menu transition",
      !/acct-menu\{[^"]*transition/.test(src),
      "declared there it would outrank the guard by load order and the guard would do nothing");
check("theme.css carries a prefers-reduced-motion block",
      /@media \(prefers-reduced-motion: reduce\)/.test(theme),
      "the app's first one; the next animated surface must find it here");
check("the guard actually neutralises transition duration",
      /prefers-reduced-motion: reduce\)\{[\s\S]*transition-duration:\s*\.01ms\s*!important/.test(theme),
      "a block that exists but neutralises nothing is the vacuous case");

console.log(failed ? "\n" + failed + " case(s) failed" : "\nall account-menu cases pass");
process.exit(failed ? 1 : 0);
