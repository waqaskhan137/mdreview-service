// Shared account menu (#132): identity + sign out, driven by /auth/session. Rendered into an #acct
// slot on every page (dashboard sidebar, account/viewer/latex-viewer top bar) so the auth UI lives in
// ONE place. Anonymous → a "Sign in" link back to the dashboard's sign-in screen.
(function () {
  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
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
    // Admin: both the indicator (you are an admin) and the way to reach /admin. Fixed violet reads on
    // every page's ground (light dashboard, dark viewer/account).
    // #262: the retired #7c6cff and the hardcoded #6a5acd are gone. Follows theme.css's .dpill /
    // .difftoggle pattern — tinted background, brand-coloured text — because the naive fix (white
    // on var(--accent)) measures 2.18:1 in dark, WORSE than the 5.31:1 it replaced. This measures
    // 6.24:1 light and 6.84:1 dark, both clearing AA.
    "#acct .acct-admin{font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;" +
    "color:var(--accent);background:var(--accent-muted);border:1px solid var(--accent);" +
    "border-radius:var(--r-pill,20px);padding:1px 7px;white-space:nowrap;flex:0 0 auto;} " +
    // #262 menu. HAND-ROLLED, not Basecoat: this file mounts on all five pages and the two
    // viewers load neither basecoat.cdn.min.css nor basecoat.all.min.js, so Basecoat is never the
    // primary here and there would be no fallback to design.
    "#acct{position:relative;}" +
    "#acct .acct-trig{display:flex;align-items:center;gap:9px;font:inherit;font-size:13px;" +
    "background:none;border:1px solid transparent;border-radius:var(--r-control,8px);" +
    "padding:3px 7px;cursor:pointer;color:inherit;max-width:min(46vw,320px);}" +
    "#acct .acct-trig:hover{border-color:var(--border);background:var(--nav-hover,transparent);}" +
    "#acct .acct-trig[aria-expanded=true]{border-color:var(--border);background:var(--nav-active,transparent);}" +
    "#acct .acct-caret{flex:0 0 auto;opacity:.55;font-size:10px;}" +
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
      // The dot stays the trigger: it encodes session liveness, and "am I still signed in?" is a
      // real recurring question here (#221, #223). No avatar — there is no identity to depict and
      // a generated initial-circle would be decoration standing in for information.
      var adminItem = sess.is_admin
        ? '<a class="acct-item" href="/admin">Admin console</a>' : "";
      el.innerHTML =
        '<button class="acct-trig" type="button" aria-haspopup="menu" aria-expanded="false">' +
          '<span class="acct-dot" title="Signed in"></span>' +
          '<span class="acct-email" title="' + esc(sess.email) + '">' + esc(sess.email) + "</span>" +
          (sess.is_admin ? '<span class="acct-admin">Admin</span>' : "") +
          '<span class="acct-caret" aria-hidden="true">\u25be</span>' +
        "</button>" +
        '<div class="acct-menu" role="menu" hidden>' +
          '<div class="acct-who"><b>' + esc(sess.email) + "</b>" +
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
