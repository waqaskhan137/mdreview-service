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
    "#acct .acct-email{color:var(--muted-fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}" +
    "#acct .acct-out{font:inherit;font-size:12.5px;font-weight:600;color:var(--text);background:none;" +
    "border:1px solid var(--rule);border-radius:8px;padding:5px 11px;cursor:pointer;flex:0 0 auto;" +
    "text-transform:none;letter-spacing:normal;}" +
    "#acct .acct-out:hover{border-color:var(--muted2,var(--muted-fg));}" +
    "#acct .acct-in{color:var(--link);text-decoration:none;font-weight:600;font-size:13px;white-space:nowrap;}" +
    "#acct .acct-in:hover{text-decoration:underline;}" +
    // Admin: both the indicator (you are an admin) and the way to reach /admin. Fixed violet reads on
    // every page's ground (light dashboard, dark viewer/account).
    // #262: the retired #7c6cff and the hardcoded #6a5acd are gone. Follows theme.css's .dpill /
    // .difftoggle pattern — tinted background, brand-coloured text — because the naive fix (white
    // on var(--brand)) measures 2.18:1 in dark, WORSE than the 5.31:1 it replaced. This measures
    // 6.24:1 light and 6.84:1 dark, both clearing AA.
    "#acct .acct-admin{font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;" +
    "color:var(--brand);background:var(--accent-bg);border:1px solid var(--brand);" +
    "border-radius:var(--r-pill,20px);padding:1px 7px;white-space:nowrap;flex:0 0 auto;} " +
    // #262 menu. HAND-ROLLED, not Basecoat: this file mounts on all five pages and the two
    // viewers load neither basecoat.cdn.min.css nor basecoat.all.min.js, so Basecoat is never the
    // primary here and there would be no fallback to design.
    "#acct{position:relative;}" +
    "#acct .acct-trig{display:flex;align-items:center;gap:9px;font:inherit;font-size:13px;" +
    "background:none;border:1px solid transparent;border-radius:var(--r-control,8px);" +
    "padding:3px 7px;cursor:pointer;color:inherit;max-width:min(46vw,320px);}" +
    "#acct .acct-trig:hover{border-color:var(--rule);background:var(--nav-hover,transparent);}" +
    "#acct .acct-trig[aria-expanded=true]{border-color:var(--rule);background:var(--nav-active,transparent);}" +
    "#acct .acct-caret{flex:0 0 auto;opacity:.55;font-size:10px;}" +
    "#acct .acct-menu{position:absolute;right:0;top:calc(100% + 6px);z-index:60;min-width:224px;" +
    "background:var(--panel,#fff);border:1px solid var(--rule);border-radius:var(--r-card,12px);" +
    "box-shadow:0 10px 30px rgba(0,0,0,.12);padding:6px;}" +
    "#acct .acct-who{padding:7px 10px 9px;border-bottom:1px solid var(--rule-faint,var(--rule));" +
    "margin-bottom:6px;}" +
    "#acct .acct-who b{display:block;font-weight:600;font-size:13px;overflow:hidden;" +
    "text-overflow:ellipsis;white-space:nowrap;}" +
    "#acct .acct-who span{font-size:11.5px;color:var(--muted2,var(--muted));}" +
    "#acct .acct-item{display:block;width:100%;text-align:left;font:inherit;font-size:13px;" +
    "padding:7px 10px;border:0;background:none;border-radius:var(--r-control,8px);cursor:pointer;" +
    "color:var(--text);text-decoration:none;}" +
    "#acct .acct-item:hover{background:var(--nav-hover,var(--inset));text-decoration:none;}" +
    "#acct .acct-sep{height:1px;background:var(--rule-faint,var(--rule));margin:6px 4px;}" +
    // sidebar variant (dashboard): pin to the bottom, stack the email above the button
    ".side #acct{margin-top:auto;padding-top:16px;border-top:1px solid var(--rule);}" +
    ".side #acct .acct{flex-wrap:wrap;}" +
    ".side #acct .acct-email{flex:1 1 100%;}";

  function inject() {
    if (document.getElementById("acct-css")) return;
    var s = document.createElement("style");
    s.id = "acct-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  async function mount() {
    var el = document.getElementById("acct");
    if (!el) return;
    inject();
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
