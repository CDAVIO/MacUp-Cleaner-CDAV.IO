/* MacUp website: theme, language, copy buttons and the Terminal demo player. */
(function () {
  "use strict";
  var root = document.documentElement;

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
  }

  /* Theme: follows the Mac until the visitor picks one. */
  var themeBtn = document.getElementById("theme");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var current = root.getAttribute("data-theme") ||
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("macup-theme", next);
    });
  }

  /* Language */
  var langSel = document.getElementById("lang");
  if (langSel) {
    langSel.addEventListener("change", function () {
      var code = langSel.value;
      store("macup-lang", code);
      location.href = (code === "en" ? "/" : "/" + code + "/") + location.hash;
    });
  }

  /* Copy buttons */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy") ? resolve() : reject(); } catch (e) { reject(e); }
      document.body.removeChild(ta);
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-copy]"), function (btn) {
    btn.addEventListener("click", function () {
      var box = btn.closest("[data-copy-box]");
      var text = box.querySelector("[data-copy-text]").textContent.trim();
      copyText(text).then(function () {
        btn.textContent = btn.getAttribute("data-done");
        btn.classList.add("done");
        setTimeout(function () { btn.textContent = btn.getAttribute("data-label"); btn.classList.remove("done"); }, 1800);
      }, function () {
        var range = document.createRange();
        range.selectNodeContents(box.querySelector("[data-copy-text]"));
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
      });
    });
  });

  /* ── Terminal demo player ─────────────────────────────────────────── */
  var player = document.getElementById("player");
  var dataEl = document.getElementById("demo-data");
  if (!player || !dataEl) return;

  var chapters = JSON.parse(dataEl.textContent).chapters;
  var screen = document.getElementById("screen");
  var pdfStage = document.getElementById("pdfstage");
  var playBtn = document.getElementById("playbtn");
  var progress = document.getElementById("progress");
  var caption = document.getElementById("caption");
  var chapterBtns = player.querySelectorAll("[data-ch]");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var state = { ch: 0, line: 0, playing: false, token: 0, done: false, started: false, preview: false };
  var MAX_LINES = 70;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function bar(p) {
    var b = el("span", "tbar"); var s = el("span"); s.style.setProperty("--p", p + "%"); b.appendChild(s); return b;
  }

  function render(l) {
    var ln = el("div", "ln");
    switch (l.k) {
      case "title":
        ln.className += " title";
        ln.appendChild(el("span", "n", l.n)); ln.appendChild(document.createTextNode(l.t)); break;
      case "rule": ln.className += " rule"; break;
      case "blank": break;
      case "text": ln.className += " " + (l.c || ""); ln.textContent = l.t; break;
      case "group": ln.className += " group"; ln.textContent = l.t; break;
      case "spin": ln.className += " spin dim"; ln.textContent = l.t; break;
      case "input": ln.className += " input y"; ln.textContent = "› " + l.t; break;
      case "opt": {
        var r = el("div", "row");
        r.appendChild(el("span", "opt", "  " + l.n));
        r.appendChild(el("span", "chk", l.on ? "✓" : " "));
        r.appendChild(el("span", "lb", l.l));
        r.appendChild(el("span", "sz", l.v));
        r.appendChild(el("span", "xt", l.x));
        ln.appendChild(r); break;
      }
      case "row": {
        var rr = el("div", "row");
        rr.appendChild(el("span", "ic " + l.s, l.i));
        rr.appendChild(el("span", "lb", l.l));
        if (l.b !== undefined) rr.appendChild(bar(l.b));
        rr.appendChild(el("span", "vl", l.v));
        if (l.x) rr.appendChild(el("span", "xt", l.x));
        ln.appendChild(rr); break;
      }
      case "proc": {
        var rp = el("div", "row");
        rp.appendChild(el("span", "ic info", " "));
        rp.appendChild(el("span", "lb", l.l));
        rp.appendChild(el("span", "vl dim", l.v));
        ln.appendChild(rp); break;
      }
      case "score": {
        var rs = el("div", "row");
        rs.appendChild(el("span", "ic", " "));
        rs.appendChild(el("span", "lb", l.l));
        rs.appendChild(bar(l.p));
        rs.appendChild(el("span", "pct", l.p + "%"));
        if (l.x) rs.appendChild(el("span", "xt", l.x));
        ln.appendChild(rs); break;
      }
      case "big": {
        ln.className += " big";
        var rb = el("div", "row");
        rb.appendChild(el("span", "lb", l.l));
        rb.appendChild(bar(l.p));
        rb.appendChild(el("span", "vl y", l.p + "%  " + l.g));
        ln.appendChild(rb); break;
      }
      case "rec": {
        ln.className += " rec";
        var head = el("div", "row");
        head.appendChild(el("span", "ic " + l.s, l.i));
        head.appendChild(el("span", "", l.t));
        ln.appendChild(head);
        ln.appendChild(el("span", "d", l.d));
        if (l.c) ln.appendChild(el("span", "c", l.c));
        break;
      }
      case "saved":
        ln.appendChild(el("span", "ok", "✓ "));
        ln.appendChild(document.createTextNode(l.t));
        ln.appendChild(document.createElement("br"));
        ln.appendChild(el("span", "y", "   " + l.p));
        break;
    }
    return ln;
  }

  function delayFor(l) {
    switch (l.k) {
      case "title": return 380;
      case "rule": return 140;
      case "blank": return 90;
      case "text": return l.c && l.c.indexOf("dim") > -1 ? 520 : 300;
      case "group": return 240;
      case "opt": return 170;
      case "row": return 140;
      case "proc": return 120;
      case "score": return 190;
      case "big": return 700;
      case "rec": return 900;
      case "input": return 700;
      case "saved": return 600;
      default: return 120;
    }
  }

  function push(node) {
    screen.appendChild(node);
    while (screen.childNodes.length > MAX_LINES) screen.removeChild(screen.firstChild);
    screen.scrollTop = screen.scrollHeight;
  }

  function setProgress() {
    var c = chapters[state.ch];
    var within = c.pdf ? Math.min(state.line, 1) : (c.lines.length ? state.line / c.lines.length : 1);
    progress.style.width = ((state.ch + within) / chapters.length * 100).toFixed(2) + "%";
  }

  function markChapter() {
    Array.prototype.forEach.call(chapterBtns, function (b, i) {
      b.classList.toggle("on", i === state.ch);
      b.setAttribute("aria-current", i === state.ch ? "step" : "false");
    });
    caption.textContent = chapters[state.ch].cap;
  }

  function setPlaying(on) {
    state.playing = on;
    player.classList.toggle("playing", on);
    var label = on ? player.getAttribute("data-pause") : (state.done ? player.getAttribute("data-replay") : player.getAttribute("data-play"));
    playBtn.setAttribute("aria-label", label);
    playBtn.title = label;
  }

  function wait(ms, token, fn) {
    setTimeout(function () { if (token === state.token && state.playing) fn(); }, ms);
  }

  function startChapter(i, instant) {
    state.token++;
    state.ch = i; state.line = 0; state.done = false;
    screen.textContent = "";
    pdfStage.hidden = true;
    markChapter();
    var c = chapters[i];
    if (c.pdf) {
      pdfStage.hidden = false;
      // Restart the pop animation.
      var paper = pdfStage.querySelector(".paper");
      if (paper) { paper.style.animation = "none"; void paper.offsetWidth; paper.style.animation = ""; }
      state.line = instant ? 1 : 0;
      setProgress();
      return;
    }
    var cmd = el("div", "ln cmd");
    cmd.appendChild(el("span", "p", "$ "));
    var typed = el("span", "", instant ? c.cmd : "");
    cmd.appendChild(typed);
    if (!instant) cmd.appendChild(el("span", "caret"));
    push(cmd);
    if (instant) {
      c.lines.forEach(function (l) { if (l.k !== "spin") push(render(l)); });
      state.line = c.lines.length;
    }
    setProgress();
    return typed;
  }

  function typeCommand(typed, text, token, then) {
    var n = 0;
    (function step() {
      if (token !== state.token || !state.playing) return;
      n++;
      typed.textContent = text.slice(0, n);
      if (n < text.length) setTimeout(step, 55 + Math.random() * 45);
      else setTimeout(function () {
        if (token !== state.token || !state.playing) return;
        var caret = typed.parentNode.querySelector(".caret");
        if (caret) caret.remove();
        then();
      }, 450);
    })();
  }

  function nextLine(token) {
    var c = chapters[state.ch];
    if (c.pdf) {
      wait(5200, token, function () { state.line = 1; setProgress(); finishChapter(token); });
      return;
    }
    if (state.line >= c.lines.length) { finishChapter(token); return; }
    var l = c.lines[state.line];
    if (l.k === "spin") {
      var s = render(l); push(s);
      wait(l.ms || 1200, token, function () { s.remove(); state.line++; setProgress(); nextLine(token); });
      return;
    }
    push(render(l));
    state.line++;
    setProgress();
    wait(delayFor(l), token, function () { nextLine(token); });
  }

  function finishChapter(token) {
    if (state.ch < chapters.length - 1) {
      wait(2400, token, function () { playFrom(state.ch + 1); });
    } else {
      state.done = true;
      setPlaying(false);
    }
  }

  function playFrom(i) {
    state.preview = false;
    setPlaying(true);
    var typed = startChapter(i, false);
    var token = state.token;
    var c = chapters[i];
    if (c.pdf) { nextLine(token); return; }
    setTimeout(function () { typeCommand(typed, c.cmd, token, function () { nextLine(token); }); }, 350);
  }

  function resume() {
    setPlaying(true);
    var token = ++state.token;
    var c = chapters[state.ch];
    if (!c.pdf && state.line >= c.lines.length) { finishChapter(token); return; }
    nextLine(token);
  }

  playBtn.addEventListener("click", function () {
    state.started = true;
    if (state.playing) { setPlaying(false); state.token++; return; }
    if (state.done) { playFrom(0); return; }
    if (state.preview) { playFrom(state.ch); return; }
    resume();
  });

  Array.prototype.forEach.call(chapterBtns, function (b) {
    b.addEventListener("click", function () {
      state.started = true;
      var i = +b.getAttribute("data-ch");
      if (reduced) { setPlaying(false); startChapter(i, true); state.preview = true; return; }
      playFrom(i);
    });
  });

  // First frame: the first chapter, fully shown, so the box is never empty.
  startChapter(0, true);
  state.preview = true;
  setPlaying(false);
  progress.style.width = "0%";

  if (!reduced && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !state.started) {
          state.started = true;
          playFrom(0);
          io.disconnect();
        }
      });
    }, { threshold: 0.45 });
    io.observe(player);
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden && state.playing) { setPlaying(false); state.token++; }
  });
})();
