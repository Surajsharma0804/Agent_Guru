/* The everyday window. It draws what the server reports: the orb's state comes
   from pipeline events, the turns from the turn record, questions from the
   orchestrator, components from the journal. There are no timers that change
   a state; the only timer asks the server what is true now. */
(function () {
  "use strict";
  var token = (location.hash.match(/t=([A-Za-z0-9_\-]+)/) || [])[1] || "";
  var startTab = (location.hash.match(/tab=([a-z]+)/) || [])[1] || "talk";
  history.replaceState(null, "", location.pathname);
  var S = {}, tab = "talk", last = null, lastGen = null, studioDrawn = false, keysDrawn = false, seenLog = 0;
  var TABS = ["talk", "tasks", "studio", "control", "doctor"];

  function $(id) { return document.getElementById(id); }
  function t(key) { return S[key] !== undefined ? S[key] : key; }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); });
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function api(method, path, body) {
    var opts = { method: method, headers: { "X-Genesis-Token": token } };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    return fetch(path, opts).then(function (r) { return r.json().then(function (j) { j._status = r.status; return j; }); });
  }
  function say(text) { $("live").textContent = text; }
  function rows(id) { var n = $(id); n.textContent = ""; return n; }

  function show(name) {
    tab = name;
    TABS.forEach(function (n) {
      $("p-" + n).classList.toggle("active", n === name);
      var b = $("t-" + n); b.setAttribute("aria-selected", String(n === name)); b.tabIndex = n === name ? 0 : -1;
    });
    if (name === "tasks") loadTasks();
    if (name === "studio") loadStudio();
    refresh();
  }

  function drawTabs() {
    var box = $("tabs");
    TABS.forEach(function (n, i) {
      var b = el("button", { role: "tab", id: "t-" + n, type: "button", class: "tab", "aria-controls": "p-" + n }, t("ws.tab." + n));
      b.addEventListener("click", function () { show(n); });
      b.addEventListener("keydown", function (e) {
        var d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!d) return;
        var next = TABS[(i + d + TABS.length) % TABS.length];
        show(next); $("t-" + next).focus();
      });
      box.appendChild(b);
    });
  }

  function drawTalk(w) {
    var orb = $("orb");
    if (orb.dataset.state !== w.orb || !orb.hasAttribute("aria-label")) { orb.dataset.state = w.orb; orb.setAttribute("aria-label", t("ws.orb." + w.orb)); $("orb-label").textContent = t("ws.orb." + w.orb); }
    var mute = $("mute"), muted = w.microphone === "muted";
    mute.disabled = w.microphone === "none";
    mute.setAttribute("aria-pressed", String(muted));
    mute.textContent = t(w.microphone === "none" ? "ws.nomic" : muted ? "ws.unmute" : "ws.mute");
    $("queue").hidden = !w.waiting;
    $("queue").textContent = w.waiting ? t("ws.waiting").replace("{n}", w.waiting) : "";
    var box = rows("questions");
    w.questions.forEach(function (q) {
      var card = el("div", { class: "panel question" });
      card.appendChild(el("p", { class: "dim" }, t(q.source === w.source ? "ws.q.typed" : "ws.q.spoken").replace("{turn}", q.turn)));
      card.appendChild(el("p", {}, q.question));
      if (q.source === w.source) {
        [["ws.yes", true, "btn small"], ["ws.no", false, "btn secondary small"]].forEach(function (b) {
          var btn = el("button", { class: b[2], type: "button" }, t(b[0]));
          btn.addEventListener("click", function () { api("POST", "/api/answer", { source: q.source, turn: q.turn, yes: b[1] }).then(refresh); });
          card.appendChild(btn);
        });
      } else {
        card.appendChild(el("p", { class: "dim" }, t("ws.q.byvoice")));
      }
      box.appendChild(card);
    });
    var list = rows("turns");
    w.turns.forEach(function (r) {
      var li = el("li", { class: "turn" });
      li.appendChild(el("span", { class: "who" }, t(r.source === w.source ? "ws.typed" : r.source === "voice" ? "ws.spoken" : "ws.other")));
      if (r.heard) li.appendChild(el("p", { class: "heard" }, r.heard));
      li.appendChild(el("p", { class: r.said ? "said" : "dim" }, r.said || t("ws.working")));
      if (r.sources && r.sources.length) {
        var src = el("ol", { class: "sources" });
        r.sources.forEach(function (s) {
          src.appendChild(el("li", {}, typeof s === "string" ? s : (s.title || s.url || JSON.stringify(s))));
        });
        li.appendChild(src);
      }
      list.appendChild(li);
    });
  }

  function loadTasks() {
    api("GET", "/api/tasks").then(function (j) {
      var ul = rows("tasks");
      if (!(j.tasks || []).length) ul.appendChild(el("li", { class: "dim" }, t("ws.notasks")));
      (j.tasks || []).forEach(function (r) {
        var li = el("li");
        li.appendChild(el("span", { class: "mark " + (r.enabled ? "ok" : "unsupported") }));
        li.appendChild(el("span", {}, r.kind));
        li.appendChild(el("span", { class: "value" }, r.message));
        ul.appendChild(li);
      });
    });
  }

  function loadStudio() {
    api("GET", "/api/settings").then(function (j) {
      if (studioDrawn) return;
      studioDrawn = true;
      var box = rows("studio"), groups = {};
      j.controls.forEach(function (c) {
        if (!groups[c.group]) { groups[c.group] = el("div", { class: "panel" }); groups[c.group].appendChild(el("h3", {}, c.group)); box.appendChild(groups[c.group]); }
        var row = el("label", { class: "tier" });
        row.appendChild(el("span", {}, c.label));
        var input;
        if (c.control === "flag") { input = el("input", { type: "checkbox" }); input.checked = !!c.value; }
        else if (c.control === "choice") {
          input = el("select");
          c.choices.forEach(function (o) { input.appendChild(el("option", { value: o }, o)); });
          if (c.value) input.value = c.value;
        } else { input = el("input", { type: c.control === "number" ? "number" : "text", value: c.value === null || c.value === undefined ? "" : c.value }); }
        input.dataset.key = c.key;
        input.addEventListener("change", function () {
          api("POST", "/api/setting", { key: c.key, value: c.control === "flag" ? input.checked : input.value }).then(function (r) {
            say(r.error || t("ws.saved"));
          });
        });
        row.appendChild(input);
        groups[c.group].appendChild(row);
      });
      if (keysDrawn) return;
      keysDrawn = true;
      var keys = rows("keys");
      Object.keys(j.credentials).forEach(function (name) {
        var row = el("label", { class: "tier" });
        var state = el("span", {}, name + ": " + t(j.credentials[name] === "set" ? "ws.key.set" : "ws.key.notset"));
        row.appendChild(state);
        var input = el("input", { type: "password", autocomplete: "off", "aria-label": name });
        input.addEventListener("change", function () {
          api("POST", "/api/credential", { name: name, value: input.value }).then(function (r) {
            input.value = "";
            if (r.state === "set") state.textContent = name + ": " + t("ws.key.set");
            say(r.error || t("ws.saved"));
          });
        });
        row.appendChild(input); keys.appendChild(row);
      });
    });
  }

  function drawControl(g) {
    var body = rows("control");
    Object.keys(g.titles).forEach(function (id) {
      var info = g.titles[id], on = g.installed.indexOf(id) >= 0, tr = el("tr");
      tr.appendChild(el("td", {}, info.title));
      tr.appendChild(el("td", { class: "state-label state-" + (on ? "verified" : "skipped") }, t(on ? "state.verified" : "ws.notinstalled")));
      var cell = el("td");
      [[on ? "repair" : "install", on ? "ws.repair" : "ws.install"]].concat(on && info.tier !== "core" ? [["remove", "ws.remove"]] : []).forEach(function (a) {
        var b = el("button", { class: "btn secondary small", type: "button" }, t(a[1]));
        b.disabled = !!g.running;
        b.addEventListener("click", function () { api("POST", "/api/component", { id: id, action: a[0] }).then(function (r) { say(r.error || t("ws.started")); refresh(); }); });
        cell.appendChild(b);
      });
      tr.appendChild(cell); body.appendChild(tr);
    });
    api("GET", "/api/events?after=" + seenLog).then(function (j) {
      (j.events || []).forEach(function (e) {
        seenLog = e.seq;
        if (e.kind === "progress" || e.kind === "log") return;
        $("history").textContent += new Date(e.ts * 1000).toLocaleString() + "  " + e.component_id + "  " + e.kind + "\n";
      });
    });
  }

  function drawDoctor(g) {
    var ul = rows("doctor");
    Object.keys(g.components).forEach(function (id) {
      var c = g.components[id], d = c.detail || {}, label = d.result || c.state;
      if (c.state === "started") label = "started";
      var li = el("li");
      li.appendChild(el("span", { class: "state-label state-" + label.replace(/ /g, "_") }, label));
      li.appendChild(el("span", {}, g.titles[id] ? g.titles[id].title : id));
      var info = el("span", { class: "value" }, d.explanation || d.detail || c.error || "");
      if (["FAILED", "NOT INSTALLED", "failed"].indexOf(label) >= 0) {
        var fix = el("button", { class: "btn small", type: "button" }, t("ws.repair"));
        fix.addEventListener("click", function () { api("POST", "/api/component", { id: id, action: "repair" }).then(function (r) { say(r.error || t("ws.started")); }); });
        info.appendChild(fix);
      }
      li.appendChild(info); ul.appendChild(li);
    });
  }

  function refresh() {
    return api("GET", "/api/workspace").then(function (w) {
      last = w;
      if (tab === "talk" && w.orb !== undefined) drawTalk(w);
      if (tab === "control" || tab === "doctor") {
        return api("GET", "/api/state").then(function (g) {
          if (g.titles === undefined) { $("control-lede").textContent = t("ws.control.none"); return; }
          lastGen = g;
          if (tab === "control") drawControl(g); else drawDoctor(g);
        });
      }
    });
  }

  fetch("ui/strings.en.json").then(function (r) { return r.json(); }).then(function (strings) {
    S = strings;
    document.querySelectorAll("[data-s]").forEach(function (n) { n.textContent = t(n.getAttribute("data-s")); });
    document.querySelectorAll("[data-p]").forEach(function (n) { n.setAttribute("placeholder", t(n.getAttribute("data-p"))); });
    drawTabs();
    $("say").addEventListener("submit", function (e) {
      e.preventDefault();
      var box = $("text"), text = box.value.trim();
      if (!text) return;
      box.value = "";
      api("POST", "/api/turn", { text: text }).then(function (r) { if (r.error) say(r.error); refresh(); });
    });
    $("text").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("say").requestSubmit(); }
    });
    $("mute").addEventListener("click", function () {
      api("POST", "/api/mic", { muted: !(last && last.microphone === "muted") }).then(refresh);
    });
    $("run-doctor").addEventListener("click", function () { api("POST", "/api/verify", {}).then(refresh); });
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
    show(TABS.indexOf(startTab) >= 0 ? startTab : "talk");
    setInterval(refresh, 400);
    setInterval(function () { api("POST", "/api/heartbeat", {}); }, 10000);
  });
})();
