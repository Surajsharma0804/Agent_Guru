/* The GENESIS window. It renders what /api/state returns and keeps no install
   state of its own: node colours, progress bars and results are all read from
   the journal by the server. The secret arrives in the URL fragment and is
   removed from the address bar at once. */
(function () {
  "use strict";
  var token = (location.hash.match(/t=([A-Za-z0-9_\-]+)/) || [])[1] || "";
  /* A replay may open on a given screen; it changes only what is shown. */
  var startScreen = (location.hash.match(/screen=([a-z]+)/) || [])[1] || "opening";
  history.replaceState(null, "", location.pathname);
  var S = {}, STAGES = [], state = null, lastSeq = 0, screen = "opening", announced = {}, core = null, coreOnline = null, coreInstall = null;
  var SCREENS = ["opening", "scan", "plan", "install", "verify", "online"];

  function $(id) { return document.getElementById(id); }
  function t(key, vars) {
    var s = S[key] !== undefined ? S[key] : key;
    Object.keys(vars || {}).forEach(function (k) { s = s.replace("{" + k + "}", vars[k]); });
    return s;
  }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); });
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function mb(bytes) { return bytes === null || bytes === undefined ? "unknown" : (bytes / 1e6).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " MB"; }
  function api(method, path, body) {
    var opts = { method: method, headers: { "X-Genesis-Token": token } };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    return fetch(path, opts).then(function (r) { return r.json().then(function (j) { j._status = r.status; return j; }); });
  }

  function show(name) {
    screen = name;
    SCREENS.forEach(function (s) { $("s-" + s).classList.toggle("active", s === name); });
    var steps = $("steps"); steps.textContent = "";
    (S.steps || []).forEach(function (label, i) {
      var li = el("li", {}, label);
      if (SCREENS[i] === name) li.setAttribute("aria-current", "step");
      steps.appendChild(li);
    });
    var h = document.querySelector("#s-" + name + " h1, #s-" + name + " h2");
    if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
  }

  function renderProbes(rows) {
    var ul = $("probe-rows");
    for (var i = ul.children.length; i < rows.length; i++) {
      var p = rows[i], li = el("li");
      li.appendChild(el("span", { class: "mark " + p.status, "aria-hidden": "true" }));
      li.appendChild(el("span", {}, p.label));
      var value = p.status === "ok" ? (typeof p.value === "string" ? p.value : JSON.stringify(p.value)) : p.status + ": " + p.reason;
      li.appendChild(el("span", { class: "value" }, value === "null" ? "none found" : value));
      ul.appendChild(li);
    }
  }

  function renderPlan(plan) {
    var tiers = $("tiers"); tiers.textContent = "";
    Object.keys(plan.tiers).forEach(function (name) {
      var label = el("label", { class: "tier" });
      var cost = plan.components.filter(function (r) { return r.tier === name && r.action === "install"; })
        .reduce(function (a, r) { return a + (r.download_bytes || 0); }, 0);
      label.appendChild(el("span", {}, (S["tier." + name] || name) + (plan.tiers[name] ? "  (" + mb(cost) + ")" : "")));
      var box = el("input", { type: "checkbox" }); box.checked = plan.tiers[name]; box.disabled = name === "core";
      box.addEventListener("change", function () { replan(); });
      box.dataset.tier = name;
      label.appendChild(box); tiers.appendChild(label);
    });
    var m = plan.model;
    $("model").textContent = m.name ? m.name + " - " + (m.reused ? "already installed" : "to download, " + mb(m.download_bytes)) + "; " + m.note : (m.error || "none");
    var a = $("arith"), tt = plan.totals; a.textContent = "";
    [["plan.download", tt.download_bytes], ["plan.keep", tt.disk_bytes], ["plan.needed", tt.needed_with_margin_bytes],
     ["plan.free", tt.free_bytes]].forEach(function (row, i) {
      a.appendChild(el("span", i === 2 ? { class: "total" } : {}, t(row[0])));
      a.appendChild(el("span", i === 2 ? { class: "total" } : {}, mb(row[1])));
    });
    function list(id, items, fmt) {
      var ul = $(id); ul.textContent = "";
      if (!items.length) ul.appendChild(el("li", { class: "dim" }, t("plan.none")));
      items.forEach(function (x) { ul.appendChild(el("li", {}, fmt(x))); });
    }
    list("outside", plan.outside_install, function (o) { return o.change; });
    list("unavailable", plan.unavailable, function (u) { return u.feature + ": " + u.why; });
    list("irreversible", plan.irreversible, function (id) { return state.titles[id] ? state.titles[id].title : id; });
    var unknown = plan.unverified_sizes.map(function (id) { return state.titles[id] ? state.titles[id].title : id; });
    $("unverified").hidden = !unknown.length;
    $("unverified").textContent = t("plan.unverified") + " " + unknown.join(", ");
    var problem = plan.path_problem || (plan.totals.fits === false ? "not enough free disk space" : "");
    $("plan-problem").hidden = !problem; $("plan-problem").textContent = problem ? t("plan.cannot") + " " + problem : "";
    $("install").disabled = !!problem || !$("approve").checked;
  }

  function replan() {
    var tiers = {};
    document.querySelectorAll("#tiers input").forEach(function (b) { tiers[b.dataset.tier] = b.checked; });
    $("approve").checked = false;
    return api("POST", "/api/plan", { tiers: tiers }).then(function (j) { if (j.plan) { state.plan = j.plan; state.plan_id = j.plan_id; renderPlan(j.plan); } });
  }

  function renderStages(st) {
    var box = $("stages");
    if (!box.children.length) STAGES.forEach(function (stage) {
      var d = el("div", { class: "stage" }); d.appendChild(el("div", { class: "node", "data-stage": stage }));
      d.appendChild(el("div", {}, t("stage." + stage))); box.appendChild(d);
    });
    STAGES.forEach(function (stage, i) {
      var cell = box.children[i], node = cell.querySelector(".node"), s = st[stage];
      node.dataset.state = s.state;
      node.setAttribute("aria-label", t("stage." + stage) + ": " + s.state);
      var old = cell.querySelector("details"); if (old) old.remove();
      if (s.state === "fractured") {
        /* The real error, one click away, inline rather than in a blocking dialog. */
        var d = el("details");
        d.appendChild(el("summary", {}, t("install.error")));
        d.appendChild(el("div", { class: "err" }, Object.keys(s.errors).map(function (k) { return k + ": " + s.errors[k]; }).join("\n\n")));
        cell.appendChild(d);
      }
    });
    if (core) core.update(st, STAGES);
    if (coreOnline) coreOnline.update(st, STAGES);
    if (coreInstall) coreInstall.update(st, STAGES);
  }

  function renderComponents() {
    var body = $("component-rows"); body.textContent = "";
    var rows = state.plan ? state.plan.components : Object.keys(state.components).map(function (id) {
      return { id: id, title: state.titles[id] ? state.titles[id].title : id, action: "install", download_bytes: null };
    });
    rows.forEach(function (r) {
      if (r.action === "skip") return;
      var c = state.components[r.id] || { state: "not started" }, tr = el("tr");
      tr.appendChild(el("td", {}, r.title));
      var st = el("td", { class: "state-label state-" + c.state.replace(" ", "_") }, t("state." + c.state));
      if (c.error) st.appendChild(el("div", { class: "err" }, c.error));
      tr.appendChild(st);
      tr.appendChild(el("td", { class: "mono" }, r.action === "reuse" ? "reused" : r.download_bytes === null ? "" : mb(r.download_bytes)));
      var td = el("td");
      if (c.state === "started") {
        var p = el("progress");
        if (c.total) { p.max = c.total; p.value = c.done; p.setAttribute("aria-label", r.title + " " + c.done + " of " + c.total); }
        td.appendChild(p);  /* no total: an indeterminate bar, never an invented percentage */
      }
      tr.appendChild(td); body.appendChild(tr);
      if (["verified", "reused", "failed", "skipped", "cancelled"].indexOf(c.state) >= 0 && announced[r.id] !== c.state) {
        announced[r.id] = c.state;
        $("live").textContent = t("live.done", { title: r.title, state: t("state." + c.state) });
      }
    });
  }

  function pollLog() {
    return api("GET", "/api/events?after=" + lastSeq).then(function (j) {
      var pre = $("log");
      (j.events || []).forEach(function (e) {
        lastSeq = e.seq;
        var extra = e.data.error || e.data.line || e.data.detail || e.data.message || (e.kind === "progress" ? e.data.done + "/" + (e.data.total || "?") : "");
        pre.textContent += new Date(e.ts * 1000).toLocaleTimeString() + "  " + e.component_id + "  " + e.kind + (extra ? "  " + extra : "") + "\n";
      });
    });
  }

  function renderResults() {
    var ul = $("results"); ul.textContent = "";
    Object.keys(state.components).forEach(function (id) {
      var c = state.components[id], d = c.detail || {}, label = d.result || c.state;
      var needs = d.needs_person && state.confirmations[id] === undefined;
      if (needs) label = "UNVERIFIED";
      if (state.confirmations[id] === false) label = "FAILED";
      var li = el("li");
      li.appendChild(el("span", { class: "state-label state-" + label.replace(/ /g, "_") }, label));
      li.appendChild(el("span", {}, state.titles[id] ? state.titles[id].title : id));
      var info = el("span", { class: "value" }, d.detail || c.error || "");
      if (needs) {
        info.appendChild(el("div", { class: "dim" }, d.needs_person));
        [["verify.heard", true], ["verify.notheard", false]].forEach(function (b) {
          var btn = el("button", { class: "btn secondary small", type: "button" }, t(b[0]));
          btn.addEventListener("click", function () { api("POST", "/api/confirm", { component: id, confirmed: b[1] }).then(refresh); });
          info.appendChild(btn);
        });
      }
      li.appendChild(info); ul.appendChild(li);
    });
  }

  function refresh() {
    return api("GET", "/api/state").then(function (s) {
      state = s;
      if (s.replay) { $("replay").hidden = false; $("replay").textContent = s.replay_label; }
      STAGES = Object.keys(s.stages);
      if (screen === "scan") { renderProbes(s.probes); $("to-plan").disabled = s.scanning || !s.probes.length; }
      if (screen === "install" && !coreInstall) coreInstall = window.GuruCore.mount($("core-install"));
      if (screen === "install" || screen === "verify" || screen === "online") renderStages(s.stages);
      if (screen === "install") {
        renderComponents();
        var finished = !s.running && s.summary;
        $("to-verify").hidden = !finished;
        $("retry").hidden = !(finished && (Object.keys(s.summary.failed || {}).length || (s.summary.cancelled || []).length));
        pollLog();
      }
      if (screen === "verify") renderResults();
      if (screen === "online") {
        var ready = s.installed.indexOf("first-start") >= 0;
        $("launch").disabled = !ready || !!s.replay;
        $("online-lede").textContent = ready ? t("online.lede") : t("online.notready");
      }
    });
  }

  function wire() {
    $("start").addEventListener("click", function () { api("POST", "/api/scan", {}).then(function () { show("scan"); }); });
    $("req-toggle").addEventListener("click", function () {
      var r = $("req"); r.hidden = !r.hidden; $("req-toggle").setAttribute("aria-expanded", String(!r.hidden));
    });
    $("to-plan").addEventListener("click", function () {
      api("POST", "/api/plan", {}).then(function (j) { state.plan = j.plan; state.plan_id = j.plan_id; renderPlan(j.plan); show("plan"); });
    });
    $("approve").addEventListener("change", function () { if (state.plan) renderPlan(state.plan); });
    function start() { return api("POST", "/api/install", { plan_id: state.plan_id }).then(function () { show("install"); }); }
    $("install").addEventListener("click", start);
    $("retry").addEventListener("click", start);
    $("cancel").addEventListener("click", function () { api("POST", "/api/cancel", {}); });
    $("pause").addEventListener("click", function () { api("POST", "/api/pause", {}); });
    $("to-verify").addEventListener("click", function () { api("POST", "/api/verify", {}).then(function () { show("verify"); }); });
    $("to-online").addEventListener("click", function () { show("online"); if (!coreOnline) coreOnline = window.GuruCore.mount($("core-online")); });
    $("launch").addEventListener("click", function () {
      $("launch").disabled = true;
      api("POST", "/api/launch", {}).then(function () {
        var wait = setInterval(function () {
          api("GET", "/api/launched").then(function (j) {
            if (j.url) { clearInterval(wait); location.replace(j.url); }
          });
        }, 500);
      });
    });
    $("show-report").addEventListener("click", function () {
      api("GET", "/api/report").then(function (r) { delete r._status; $("report").hidden = false; $("report").textContent = JSON.stringify(r, null, 1); });
    });
    $("export").addEventListener("click", function () {
      api("GET", "/api/report").then(function (r) {
        delete r._status;
        var a = el("a", { download: "agent-guru-report.json" });
        a.href = URL.createObjectURL(new Blob([JSON.stringify(r, null, 1)], { type: "application/json" }));
        document.body.appendChild(a); a.click(); a.remove();
      });
    });
    $("contrast").addEventListener("click", function () {
      var on = document.documentElement.dataset.contrast !== "high";
      document.documentElement.dataset.contrast = on ? "high" : "";
      $("contrast").setAttribute("aria-pressed", String(on));
    });
    window.addEventListener("beforeunload", function () {
      fetch("/api/close", { method: "POST", keepalive: true,
        headers: { "X-Genesis-Token": token, "Content-Type": "application/json" }, body: "{}" });
    });
  }

  fetch("ui/strings.en.json").then(function (r) { return r.json(); }).then(function (strings) {
    S = strings;
    document.documentElement.lang = S.lang;
    document.querySelectorAll("[data-s]").forEach(function (n) { n.textContent = t(n.getAttribute("data-s")); });
    wire();
    show(SCREENS.indexOf(startScreen) >= 0 ? startScreen : "opening");
    core = window.GuruCore.mount($("core"));
    window.GenesisDebug = { core: function () { return core && core.stats; }, install: function () { return coreInstall && coreInstall.stats; }, state: function () { return state; } };
    refresh();
    setInterval(refresh, 500);
    setInterval(function () { api("POST", "/api/heartbeat", {}); }, 10000);
  });
})();
