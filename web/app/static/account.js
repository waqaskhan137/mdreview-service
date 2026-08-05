// Shared account menu (#132): identity + sign out, driven by /auth/session. Rendered into an #acct
// slot on every page (dashboard sidebar, account/viewer/latex-viewer top bar) so the auth UI lives in
// ONE place. Anonymous → a "Sign in" link back to the dashboard's sign-in screen.
(function () {
  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  // Always exactly two characters (AC1), even for a pathological one-character source: pad by
  // repeating the first char, and "u" is the last-resort floor when there is nothing to derive from.
  function twoChars(s) {
    if (!s) s = "u";
    if (s.length < 2) s += s[0];
    return s.slice(0, 2);
  }
  // #281 Q6: two-character trigger initials, derived from the email when no display name is set.
  // "a.kerr@x.com" -> "ak" (first letter of the first two dot/underscore/hyphen-split local-part
  // segments); a local part with no such split falls back to its own first two characters.
  function initials(email) {
    var local = String(email || "").split("@")[0].toLowerCase();
    var segs = local.split(/[._-]+/).filter(Boolean);
    var s = segs.length >= 2 ? segs[0][0] + segs[1][0] : local.replace(/[^a-z0-9]/g, "").slice(0, 2);
    return twoChars(s);
  }
  // #309: once a display name is set, the trigger derives from IT instead — first letters of the
  // first two whitespace-split words ("Ada Lovelace" -> "al"), else the name's own first two
  // characters (a single-word name, e.g. "Cher" -> "ch"). Same two-character floor as initials().
  function nameInitials(name) {
    var words = String(name || "").trim().split(/\s+/).filter(Boolean);
    var s = words.length >= 2 ? words[0][0] + words[1][0] : (words[0] || "").slice(0, 2);
    return twoChars(s.toLowerCase());
  }
  var CSS =
    // normal-case + no letter-spacing so the email reads right even inside the viewer's uppercase top bar
    "#acct .acct{display:flex;align-items:center;gap:9px;font-size:13px;min-width:0;text-transform:none;letter-spacing:normal;}" +
    "#acct .acct-dot{width:7px;height:7px;border-radius:50%;background:#2f8f5b;flex:0 0 auto;}" +
    "#acct .acct-email{color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}" +
    "#acct .acct-out{font:inherit;font-size:12.5px;font-weight:600;color:var(--text);background:none;" +
    "border:1px solid var(--border);border-radius:8px;padding:5px 11px;cursor:pointer;flex:0 0 auto;" +
    "text-transform:none;letter-spacing:normal;}" +
    "#acct .acct-out:hover{border-color:var(--text-subtle,var(--text-muted));}" +
    "#acct .acct-in{color:var(--link);text-decoration:none;font-weight:600;font-size:13px;white-space:nowrap;}" +
    "#acct .acct-in:hover{text-decoration:underline;}" +
    // #281 (epic #276): the avatar-initials trigger replaces the #262 dot+email+Admin-pill+caret
    // row. Admin stays visible — in the trigger's title tooltip and in the menu's .acct-who — it
    // just no longer needs its own pill now the trigger isn't a text row with room for one.
    "#acct{position:relative;}" +
    "#acct .acct-trig{position:relative;display:flex;align-items:center;justify-content:center;" +
    "width:28px;height:28px;padding:0;font-family:var(--font-mono,'Geist Mono',monospace);" +
    "font-size:var(--t-eyebrow);font-weight:600;line-height:1;color:var(--text-muted);" +
    "background:var(--code-bg);border:1px solid var(--border);border-radius:var(--r-control,8px);" +
    "cursor:pointer;transition:border-color 160ms ease-out,color 160ms ease-out;}" +
    "#acct .acct-trig:hover,#acct .acct-trig:focus-visible,#acct .acct-trig[aria-expanded=true]{" +
    "border-color:var(--text-subtle);color:var(--text);}" +
    // The liveness dot (#221/#223: "am I still signed in?"), now the trigger's corner badge
    // instead of its leading glyph. A DISTINCT class from the three non-authenticated states'
    // .acct-dot: those stay byte-for-byte (#281 AC5), so this cannot reuse or perturb that rule.
    "#acct .acct-corner{position:absolute;right:-2px;bottom:-2px;width:8px;height:8px;" +
    "border-radius:50%;background:var(--success);border:2px solid var(--bg);}" +
    "#acct .acct-menu{position:absolute;right:0;top:calc(100% + 6px);z-index:60;min-width:224px;" +
    "background:var(--surface,#fff);border:1px solid var(--border);border-radius:var(--r-card,12px);" +
    "box-shadow:0 10px 30px rgba(0,0,0,.12);padding:6px;}" +
    "#acct .acct-who{padding:7px 10px 9px;border-bottom:1px solid var(--border-faint,var(--border));" +
    "margin-bottom:6px;}" +
    "#acct .acct-who b{display:block;font-weight:600;font-size:13px;overflow:hidden;" +
    "text-overflow:ellipsis;white-space:nowrap;}" +
    "#acct .acct-who span{font-size:11.5px;color:var(--text-subtle,var(--muted));}" +
    "#acct .acct-item{display:block;width:100%;text-align:left;font:inherit;font-size:13px;" +
    "padding:7px 10px;border:0;background:none;border-radius:var(--r-control,8px);cursor:pointer;" +
    "color:var(--text);text-decoration:none;}" +
    "#acct .acct-item:hover{background:var(--nav-hover,var(--code-bg));text-decoration:none;}" +
    "#acct .acct-sep{height:1px;background:var(--border-faint,var(--border));margin:6px 4px;}" +
    // sidebar variant (dashboard): pin to the bottom, stack the email above the button
    ".side #acct{margin-top:auto;padding-top:16px;border-top:1px solid var(--border);}" +
    ".side #acct .acct{flex-wrap:wrap;}" +
    ".side #acct .acct-email{flex:1 1 100%;}";

  function inject() {
    if (document.getElementById("acct-css")) return;
    var s = document.createElement("style");
    s.id = "acct-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ---- #285 theme toggle ------------------------------------------------------------------
  // Mode is data-theme on <html>: "light"/"dark" explicit, attribute ABSENT is auto. The
  // pre-paint applier in each <head> already applied storage; this code never resolves auto
  // into an explicit value — auto stays pure CSS so a live OS change re-themes with no JS.
  // Storage: mdr.theme holds explicit values only; choosing auto removes the key; every access
  // is try/catch so blocked storage still leaves a working per-session toggle.
  // NOT window.basecoat.theme: that rival flips a .dark class and writes a themeMode key,
  // neither of which theme.css reads — two mechanisms would fight silently (#285 AC 6 asserts
  // both stay absent). The button's CSS lives in theme.css per the #262 load-order rule.
  function themeMode() {
    var t = document.documentElement.getAttribute("data-theme");
    return t === "light" || t === "dark" ? t : "auto";
  }
  function themeEffective() {
    var m = themeMode();
    if (m !== "auto") return m;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function themeLabel() {
    return "Theme: " + (themeMode() === "auto" ? "system" : themeMode());
  }
  function themeNotify() {
    // The one effective-theme signal. JS consumers (the viewer's Mermaid re-render) track THIS,
    // never the OS: an OS listener disagrees with an explicit override.
    document.dispatchEvent(new CustomEvent("mdr:themechange", {
      detail: { mode: themeMode(), theme: themeEffective() },
    }));
  }
  function themeSet(mode) {
    if (mode === "light" || mode === "dark") document.documentElement.setAttribute("data-theme", mode);
    else document.documentElement.removeAttribute("data-theme");
    try {
      if (mode === "light" || mode === "dark") localStorage.setItem("mdr.theme", mode);
      else localStorage.removeItem("mdr.theme");
    } catch (e) { /* storage unavailable: the choice still holds for this page */ }
    var btn = document.getElementById("themetoggle");
    if (btn) btn.setAttribute("aria-label", themeLabel());
    themeNotify();
  }
  window.mdTheme = { mode: themeMode, effective: themeEffective, set: themeSet };
  if (window.matchMedia) {
    // Auto is live by CSS alone; this listener only forwards the flip to JS consumers.
    var themeMq = matchMedia("(prefers-color-scheme: dark)");
    var onOsFlip = function () { if (themeMode() === "auto") themeNotify(); };
    if (themeMq.addEventListener) themeMq.addEventListener("change", onOsFlip);
    else if (themeMq.addListener) themeMq.addListener(onOsFlip);
  }

  // Sun and moon are the mock's own glyphs (sun shown in the light screens, moon in the dark
  // ones). The mock never draws the auto state; the monitor glyph for "system" is the documented
  // judgement call (the --warning-border precedent) — owner veto at review. All three ship in the
  // button and theme.css picks one off the same data-theme state the tokens read, so the icon
  // cannot disagree with the rendered theme.
  var TT_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="';
  var TT_ICONS =
    TT_SVG + 'tt-sun"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>' +
    TT_SVG + 'tt-moon"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>' +
    TT_SVG + 'tt-auto"><rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8M12 17v4"/></svg>';

  function mountToggle(el) {
    if (document.getElementById("themetoggle")) return; // mount() re-runs after auth changes
    var btn = document.createElement("button");
    btn.id = "themetoggle";
    btn.className = "theme-toggle";
    btn.type = "button";
    btn.setAttribute("aria-label", themeLabel());
    btn.innerHTML = TT_ICONS;
    btn.addEventListener("click", function () {
      themeSet({ auto: "light", light: "dark", dark: "auto" }[themeMode()]);
    });
    // The mock's slot: immediately before the account cluster, on every page.
    el.parentNode.insertBefore(btn, el);
  }

  async function mount() {
    var el = document.getElementById("acct");
    if (!el) return;
    inject();
    // #285: the toggle mounts SYNCHRONOUSLY, before the session fetch below — theming must not
    // wait on /auth/session, and it exists even when the auth plane is absent or unreachable.
    mountToggle(el);
    // #221: "could not ask" is not "signed out". Offering a Sign in link to someone whose session
    // is alive is a lie, and it is the lie that made a server blip look like a logout.
    var res = await window.mdSession.read();
    // #224: on a build with no auth plane there is no account to show and nothing to reconnect to.
    // Render nothing rather than a permanent "Reconnecting…" or a "Sign in" link that leads nowhere.
    if (res.noAuthPlane) { el.innerHTML = ""; return; }
    if (!res.reachable) {
      el.innerHTML =
        '<div class="acct"><span class="acct-dot" style="background:#9aa0a6" title="Cannot reach the server"></span>' +
        '<span class="acct-email">Reconnecting…</span></div>';
      return;
    }
    var sess = res.sess;

    if (sess && sess.authenticated) {
      // #281 (epic #276 avatar-initials decision, reversing #262's "no avatar"): the trigger's two
      // characters are DERIVED, never chosen. #309 gave the account a real display-name field, so
      // this now prefers it (nameInitials) and falls back to the #281 email-derived heuristic
      // (initials) only while unset \u2014 documented judgement call (groom #281, Q6) for the fallback
      // itself. Always exactly two characters either way.
      var whoName = sess.name || sess.email;
      var init = sess.name ? nameInitials(sess.name) : initials(sess.email);
      var tip = esc(whoName) + (sess.is_admin ? " \u00b7 Admin" : "");
      var adminItem = sess.is_admin
        ? '<a class="acct-item" href="/admin">Admin console</a>' : "";
      el.innerHTML =
        '<button class="acct-trig" type="button" aria-haspopup="menu" aria-expanded="false" title="' + tip + '">' +
          esc(init) +
          '<span class="acct-corner" title="Signed in"></span>' +
        "</button>" +
        '<div class="acct-menu" role="menu" hidden>' +
          '<div class="acct-who"><b>' + esc(whoName) + "</b>" +
            "<span>" + (sess.is_admin ? "Admin" : "Signed in") + "</span></div>" +
          '<a class="acct-item" href="/account" role="menuitem">Account</a>' +
          adminItem +
          '<div class="acct-sep"></div>' +
          '<button class="acct-item acct-out" type="button" role="menuitem">Sign out</button>' +
        "</div>";

      var trig = el.querySelector(".acct-trig");
      var menu = el.querySelector(".acct-menu");
      var items = function () { return Array.prototype.slice.call(menu.querySelectorAll(".acct-item")); };
      var open = function (focusFirst) {
        menu.hidden = false; trig.setAttribute("aria-expanded", "true");
        if (focusFirst) { var i = items()[0]; if (i) i.focus(); }
      };
      var close = function (refocus) {
        if (menu.hidden) return false;
        menu.hidden = true; trig.setAttribute("aria-expanded", "false");
        if (refocus) trig.focus();
        return true;
      };
      trig.addEventListener("click", function () { menu.hidden ? open(false) : close(false); });
      trig.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") { e.preventDefault(); open(true); }
      });
      menu.addEventListener("keydown", function (e) {
        var list = items(), i = list.indexOf(document.activeElement);
        if (e.key === "ArrowDown") { e.preventDefault(); (list[i + 1] || list[0]).focus(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); (list[i - 1] || list[list.length - 1]).focus(); }
        else if (e.key === "Escape") { e.preventDefault(); close(true); }
      });
      document.addEventListener("click", function (e) { if (!el.contains(e.target)) close(false); });
      // Escape goes through the SHARED layer stack where keys.js is loaded, so the menu composes
      // with the ? sheet and the palette instead of racing them; the local handler above still
      // covers pages that do not load keys.js (both viewers).
      if (window.mdKeys && window.mdKeys.pushEscape) {
        window.mdKeys.pushEscape(function () { return close(true); });
      }

      el.querySelector(".acct-out").addEventListener("click", async function () {
        try {
          await fetch("/auth/logout", { method: "POST", headers: { "X-CSRF-Token": sess.csrf || "" } });
        } catch (e) { /* clear locally regardless */ }
        location.href = "/";
      });
    } else {
      el.innerHTML = '<div class="acct"><a class="acct-in" href="/">Sign in</a></div>';
    }
  }

  if (document.readyState !== "loading") mount();
  else document.addEventListener("DOMContentLoaded", mount);
  window.mdreviewAccount = mount; // let a page re-render after its own auth change
})();
