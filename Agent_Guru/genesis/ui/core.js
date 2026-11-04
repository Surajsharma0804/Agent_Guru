/* The animated core: eight rings, one per stage, coloured by the stage's state.
   A custom WebGL fragment shader (about 60 lines) instead of a 3D library: the
   whole file is a few kilobytes, where three.js alone is over 600 KB.
   Fallbacks, in order: WebGL, a 2D canvas, a static SVG diagram. With
   prefers-reduced-motion the core is drawn once, still, in its state colours.
   The loop runs at most 60 frames a second, 30 on battery, and stops while
   the window is hidden or not focused. State comes only from update(), which
   the page calls with the stage states it got from the server. */
(function () {
  "use strict";
  var STATE_INDEX = { dim: 0, building: 1, lit: 2, reused: 3, fractured: 4 };
  var STAGES = 8;

  function tokens() {
    var css = getComputedStyle(document.documentElement);
    function rgb(name) {
      var v = css.getPropertyValue(name).trim();
      var m = v.match(/^#([0-9a-f]{6})$/i);
      if (!m) return [0.3, 0.35, 0.4];
      var n = parseInt(m[1], 16);
      return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255];
    }
    var p = [rgb("--node-dim"), rgb("--accent"), rgb("--ok"), rgb("--violet"), rgb("--bad")];
    p.bg = rgb("--bg");
    return p;
  }

  var VERT = "attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }";
  var FRAG = [
    "precision mediump float;",
    "uniform vec2 res; uniform float t; uniform float st[8]; uniform vec3 pal[5]; uniform vec3 bg; uniform float still;",
    "vec3 colourFor(float s){ if(s<0.5) return pal[0]; if(s<1.5) return pal[1]; if(s<2.5) return pal[2];",
    "  if(s<3.5) return pal[3]; return pal[4]; }",
    "void main(){",
    "  vec2 uv = (gl_FragCoord.xy - 0.5*res) / min(res.x, res.y);",
    "  float r = length(uv); float a = atan(uv.y, uv.x);",
    "  vec3 col = bg;",
    "  for (int i = 0; i < 8; i++) {",
    "    float fi = float(i); float s = st[i];",
    "    float radius = 0.12 + fi * 0.045;",
    "    float speed = (mod(fi, 2.0) < 1.0 ? 1.0 : -1.0) * (0.25 + fi * 0.04) * (1.0 - still);",
    "    float seg = 0.5 + 0.5 * sin(a * (3.0 + fi) + t * speed * 2.0);",
    "    float ring = smoothstep(0.012, 0.0, abs(r - radius));",
    "    float on = s < 0.5 ? 0.22 : 1.0;",
    "    float flicker = s > 0.5 && s < 1.5 ? 0.55 + 0.45 * sin(t * 4.0 + fi) : 1.0;",
    "    float broken = s > 3.5 ? step(0.45, fract(a * 2.5 + fi)) : 1.0;",
    "    float dots = s > 2.5 && s < 3.5 ? step(0.5, fract(a * 6.0)) * 0.6 + 0.4 : 1.0;",
    "    col += colourFor(s) * ring * on * flicker * broken * dots * (0.55 + 0.45 * seg);",
    "  }",
    "  float glow = exp(-r * 7.0) * 0.9;",
    "  col += pal[1] * glow * (0.6 + 0.4 * sin(t * 1.3) * (1.0 - still));",
    "  col += vec3(0.42, 0.33, 0.85) * exp(-r * 3.0) * 0.12;",
    "  gl_FragColor = vec4(mix(bg, col, smoothstep(0.5, 0.44, r)), 1.0);",
    "}"].join("\n");

  function makeGL(canvas) {
    var gl = canvas.getContext("webgl", { antialias: true, premultipliedAlpha: false });
    if (!gl) return null;
    function sh(type, src) {
      var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    }
    var prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
    gl.useProgram(prog);
    var buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    var u = { res: gl.getUniformLocation(prog, "res"), t: gl.getUniformLocation(prog, "t"),
      st: gl.getUniformLocation(prog, "st"), pal: gl.getUniformLocation(prog, "pal"),
      still: gl.getUniformLocation(prog, "still"), bg: gl.getUniformLocation(prog, "bg") };
    return function draw(time, states, palette, still) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(u.res, canvas.width, canvas.height); gl.uniform1f(u.t, time);
      gl.uniform1fv(u.st, states); gl.uniform3fv(u.pal, [].concat.apply([], palette));
      gl.uniform3fv(u.bg, palette.bg);  /* --bg, so the canvas has no visible edge */
      gl.uniform1f(u.still, still ? 1 : 0); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
  }

  function make2D(canvas) {
    var c = canvas.getContext("2d");
    if (!c) return null;
    return function draw(time, states, palette, still) {
      var w = canvas.width, h = canvas.height, m = Math.min(w, h);
      c.fillStyle = "rgb(" + palette.bg.map(function (x) { return Math.round(x * 255); }).join(",") + ")";
      c.fillRect(0, 0, w, h);
      for (var i = 0; i < STAGES; i++) {
        var p = palette[states[i]] || palette[0];
        c.strokeStyle = "rgb(" + p.map(function (x) { return Math.round(x * 255); }).join(",") + ")";
        c.globalAlpha = states[i] === 0 ? 0.3 : 1;
        c.lineWidth = m * 0.012;
        c.setLineDash(states[i] === 4 ? [m * 0.02, m * 0.02] : states[i] === 3 ? [m * 0.006, m * 0.012] : []);
        var spin = still ? 0 : time * (i % 2 ? -0.3 : 0.3);
        c.beginPath(); c.arc(w / 2, h / 2, m * (0.12 + i * 0.045), spin, spin + Math.PI * 1.85); c.stroke();
      }
      c.globalAlpha = 1; c.setLineDash([]);
    };
  }

  function staticSVG(el, states) {
    var rings = "";
    for (var i = 0; i < STAGES; i++) {
      var s = states[i] || 0;
      rings += '<circle cx="50" cy="50" r="' + (12 + i * 4.5) + '" class="ring ring-' + s + '"/>';
    }
    el.innerHTML = '<svg viewBox="0 0 100 100" role="img" aria-label="Setup progress">' + rings + "</svg>";
  }

  function Core(el) {
    this.el = el;
    this.states = new Array(STAGES).fill(0);
    this.stats = { mode: "", frames: 0, totalMs: 0, maxMs: 0, last: 0 };
    this.reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.fpsCap = 60;
    var canvas = document.createElement("canvas");
    el.appendChild(canvas);
    this.canvas = canvas;
    try { this.draw = makeGL(canvas); this.stats.mode = this.draw ? "webgl" : ""; } catch (e) { this.draw = null; }
    if (!this.draw) { this.draw = make2D(canvas); this.stats.mode = this.draw ? "canvas2d" : ""; }
    if (!this.draw) { el.removeChild(canvas); this.stats.mode = "static"; staticSVG(el, this.states); }
    this.palette = tokens();
    this.resize();
    var self = this;
    window.addEventListener("resize", function () { self.resize(); self.frame(performance.now(), true); });
    if (navigator.getBattery) {
      navigator.getBattery().then(function (b) {
        function apply() { self.fpsCap = b.charging ? 60 : 30; }
        apply(); b.addEventListener("chargingchange", apply);
      });
    }
    this.running = false;
    document.addEventListener("visibilitychange", function () { self.schedule(); });
    window.addEventListener("focus", function () { self.schedule(); });
    window.addEventListener("blur", function () { self.schedule(); });
    this.frame(performance.now(), true);
    this.schedule();
  }
  Core.prototype.resize = function () {
    if (!this.canvas) return;
    var r = this.el.getBoundingClientRect(), d = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.max(1, Math.round(r.width * d)); this.canvas.height = Math.max(1, Math.round(r.height * d));
  };
  Core.prototype.active = function () {
    return !this.reduced && this.stats.mode !== "static" && !document.hidden && document.hasFocus();
  };
  Core.prototype.schedule = function () {
    var self = this;
    if (this.running || !this.active()) return;
    this.running = true;
    function tick(now) {
      if (!self.active()) { self.running = false; return; }
      if (now - self.stats.last >= 1000 / self.fpsCap - 1) self.frame(now, false);
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  };
  Core.prototype.frame = function (now, still) {
    if (this.stats.mode === "static") { staticSVG(this.el, this.states); return; }
    var start = performance.now();
    this.draw(now / 1000, this.states, this.palette, still || this.reduced);
    var ms = performance.now() - start;
    this.stats.frames += 1; this.stats.totalMs += ms; this.stats.maxMs = Math.max(this.stats.maxMs, ms);
    this.stats.last = now;
  };
  Core.prototype.update = function (stageStates, order) {
    var self = this;
    order.forEach(function (stage, i) {
      var s = stageStates[stage] ? stageStates[stage].state : "dim";
      self.states[i] = STATE_INDEX[s] || 0;
    });
    this.palette = tokens();
    this.frame(performance.now(), true);
    this.schedule();
  };
  window.GuruCore = { mount: function (el) { return new Core(el); } };
})();
