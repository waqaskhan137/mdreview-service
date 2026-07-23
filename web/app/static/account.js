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
    "#acct .acct-email{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}" +
    "#acct .acct-out{font:inherit;font-size:12.5px;font-weight:600;color:var(--text);background:none;" +
    "border:1px solid var(--rule);border-radius:8px;padding:5px 11px;cursor:pointer;flex:0 0 auto;" +
    "text-transform:none;letter-spacing:normal;}" +
    "#acct .acct-out:hover{border-color:var(--muted2,var(--muted));}" +
    "#acct .acct-in{color:var(--link);text-decoration:none;font-weight:600;font-size:13px;white-space:nowrap;}" +
    "#acct .acct-in:hover{text-decoration:underline;}" +
    // Admin: both the indicator (you are an admin) and the way to reach /admin. Fixed violet reads on
    // every page's ground (light dashboard, dark viewer/account).
    "#acct .acct-admin{font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;" +
    "color:#fff;background:#6a5acd;border-radius:20px;padding:3px 10px;text-decoration:none;" +
    "white-space:nowrap;flex:0 0 auto;}" +
    "#acct .acct-admin:hover{background:#7c6cff;text-decoration:none;}" +
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
    var sess = { authenticated: false };
    try {
      sess = await fetch("/auth/session", { cache: "no-store" }).then(function (r) { return r.json(); });
    } catch (e) { /* offline → treat as anonymous */ }

    if (sess && sess.authenticated) {
      var adminLink = sess.is_admin
        ? '<a class="acct-admin" href="/admin" title="Open the admin console">Admin</a>' : "";
      el.innerHTML =
        '<div class="acct"><span class="acct-dot" title="Signed in"></span>' +
        '<span class="acct-email" title="' + esc(sess.email) + '">' + esc(sess.email) + "</span>" +
        adminLink +
        '<button class="acct-out" type="button">Sign out</button></div>';
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
