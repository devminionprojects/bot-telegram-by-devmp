(function () {
var tg = window.Telegram && window.Telegram.WebApp;
try { if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor("#0d0a1f"); tg.setBackgroundColor("#0d0a1f"); } catch (e1) {} } } catch (e) {}
function hap() { try { tg.HapticFeedback.impactOccurred("light"); } catch (e) {} }
function $(i) { return document.getElementById(i); }
// animasi lewat Web Animations API; kalau tidak didukung / gagal, elemen tetap tampil statis (tidak pernah hilang)
function anim(el, kf, opt) { try { if (el && el.animate) return el.animate(kf, opt); } catch (e) {} return null; }
var INIT = (tg && tg.initData) || "";
var L = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
var mode = "menu", b = ["", "", "", "", "", "", "", "", ""], over = false, busy = false, wl = [];
var sc = {x: 0, o: 0, d: 0}, bsc = {x: 0, o: 0, d: 0};
var net = null, gid = "", timer = null, animRid = -1, hold = null;
var ANIM_MS = 2300, animT = null;
var LV = 3, NAMES = {1: "Mudah", 2: "Sedang", 3: "Sulit", 4: "Mustahil"}, bscs = {};
function blank() { return {x: 0, o: 0, d: 0}; }
try {
  var s2 = JSON.parse(localStorage.getItem("ttt_score2") || "null");
  if (s2 && typeof s2 === "object") bscs = s2;
  else { var s0 = JSON.parse(localStorage.getItem("ttt_score") || "null"); if (s0 && typeof s0.x === "number") bscs = {3: s0}; }   // skor lama dianggap level Sulit
} catch (e) {}
for (var q = 1; q <= 4; q++) if (!bscs[q] || typeof bscs[q].x !== "number") bscs[q] = blank();
bsc = bscs[LV];
function save() { try { localStorage.setItem("ttt_score2", JSON.stringify(bscs)); } catch (e) {} }
function show(v) { ["menu", "fr", "df", "gm"].forEach(function (k) { $(k).classList.toggle("hide", k !== v); }); }
// ---- tanda X / O sebagai SVG (kondisi dasar sudah tergambar penuh)
function markSVG(v) {
  if (v === "X") return '<svg viewBox="0 0 100 100"><path pathLength="1" d="M26 26L74 74"/><path pathLength="1" d="M74 26L26 74"/></svg>';
  return '<svg viewBox="0 0 100 100"><circle pathLength="1" cx="50" cy="50" r="25" transform="rotate(-90 50 50)"/></svg>';
}
(function () {
  var lg = $("logo"), seq = ["X", "", "O", "", "X", "", "O", "", "X"];
  seq.forEach(function (v, k) {
    var i = document.createElement("i"); if (v) { i.style.color = v === "X" ? "var(--x)" : "var(--o)"; i.innerHTML = markSVG(v); var s = i.firstChild; var ch = s.querySelectorAll("*"); for (var z = 0; z < ch.length; z++) { ch[z].setAttribute("fill", "none"); ch[z].setAttribute("stroke", "currentColor"); ch[z].setAttribute("stroke-width", "12"); ch[z].setAttribute("stroke-linecap", "round"); } }
    lg.appendChild(i);
  });
})();
function win(a) {
  for (var i = 0; i < L.length; i++) { var l = L[i]; if (a[l[0]] && a[l[0]] === a[l[1]] && a[l[1]] === a[l[2]]) return {w: a[l[0]], l: l}; }
  for (var j = 0; j < 9; j++) if (!a[j]) return null;
  return {w: "D", l: []};
}
var MEMO = {};
function mm(a, t, d) {
  var key = a.map(function (c) { return c || "-"; }).join("") + t + d; if (MEMO[key] !== undefined) return MEMO[key];   // sel kosong ditandai agar posisi tidak tertukar
  var res = mm0(a, t, d); MEMO[key] = res; return res;
}
function mm0(a, t, d) {
  var r = win(a);
  if (r) return r.w === "O" ? 10 - d : r.w === "X" ? d - 10 : 0;
  var best = null;
  for (var i = 0; i < 9; i++) if (!a[i]) {
    a[i] = t; var v = mm(a, t === "O" ? "X" : "O", d + 1); a[i] = "";
    if (best === null || (t === "O" && v > best) || (t === "X" && v < best)) best = v;
  }
  return best;
}
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function lineMove(p) {   // sel kosong yang melengkapi 3 sejajar untuk pemain p, atau -1
  for (var k = 0; k < L.length; k++) {
    var l = L[k], c = 0, e = -1;
    for (var j = 0; j < 3; j++) { if (b[l[j]] === p) c++; else if (!b[l[j]]) e = l[j]; }
    if (c === 2 && e >= 0) return e;
  }
  return -1;
}
function bestMove(free) {   // minimax penuh: tidak pernah kalah, secepat mungkin menang
  var top = -99, sc2 = [], i;
  for (i = 0; i < free.length; i++) { b[free[i]] = "O"; var v = mm(b, "X", 1); b[free[i]] = ""; sc2.push([v, free[i]]); if (v > top) top = v; }
  return pick(sc2.filter(function (p) { return p[0] === top; }).map(function (p) { return p[1]; }));
}
function botMove() {
  var free = [], i;
  for (i = 0; i < 9; i++) if (!b[i]) free.push(i);
  var win1 = lineMove("O"), blk = lineMove("X");
  if (LV === 1) return (win1 >= 0 && Math.random() < .25) ? win1 : pick(free);               // Mudah: asal jalan, sesekali kebetulan menang
  if (LV === 2) {                                                                              // Sedang: sering lupa menutup
    if (win1 >= 0 && Math.random() < .8) return win1;
    if (blk >= 0 && Math.random() < .55) return blk;
    return pick(free);
  }
  if (LV === 3) {                                                                              // Sulit: taktik selalu benar, strategi kadang meleset
    if (win1 >= 0) return win1;
    if (blk >= 0) return blk;
    return Math.random() < .8 ? bestMove(free) : pick(free);
  }
  return bestMove(free);                                                                       // Mustahil: sempurna
}
var g = $("g"), st = $("st"), cells = [], shown = ["", "", "", "", "", "", "", "", ""], lineKey = "";
function haptic(kind) {
  try { tg.HapticFeedback.notificationOccurred(kind === "win" ? "success" : kind === "lose" ? "error" : "warning"); }
  catch (e) { try { if (navigator.vibrate) navigator.vibrate(kind === "lose" ? [90, 50, 90] : 60); } catch (e2) {} }
}
function stopAnim() {
  clearTimeout(animT); var f = $("fx"); f.className = "fx hide"; f.textContent = "";
}
function playAnim(kind) {   // kind: win | lose | draw
  stopAnim();
  var f = $("fx"), fl = document.createElement("div"), bn = document.createElement("div"), ic = document.createElement("i"), tx = document.createElement("b");
  fl.className = "fl";
  ic.textContent = kind === "win" ? "🏆" : kind === "lose" ? "💔" : "🤝";
  tx.textContent = kind === "win" ? "MENANG!" : kind === "lose" ? "KALAH" : "SERI";
  bn.className = "bn"; bn.appendChild(ic); bn.appendChild(tx);
  f.className = "fx " + kind; f.appendChild(fl); f.appendChild(bn);   // sudah terlihat penuh tanpa animasi
  anim(fl, [{opacity: 0}, {opacity: 1, offset: .2}, {opacity: .8}], {duration: 700, easing: "ease-out"});
  if (kind === "lose") anim(bn, [{transform: "translateY(-120px) scale(1.5)", opacity: 0}, {transform: "translateY(0) scale(1)", opacity: 1}], {duration: 550, easing: "cubic-bezier(.3,1.4,.5,1)"});
  else anim(bn, [{transform: "scale(0) rotate(-14deg)", opacity: 0}, {transform: "scale(1) rotate(0deg)", opacity: 1}], {duration: 600, easing: "cubic-bezier(.2,1.7,.4,1)"});
  if (kind === "win") anim(ic, [{transform: "rotate(-10deg) scale(1)"}, {transform: "rotate(10deg) scale(1.12)"}, {transform: "rotate(-10deg) scale(1)"}], {duration: 900, iterations: 2, easing: "ease-in-out"});
  var cols = ["#ffd54a", "#ff6b81", "#4cd964", "#5ac8fa", "#af52de", "#ff9f0a"], n = kind === "draw" ? 0 : 22;
  for (var i = 0; i < n; i++) {
    var p = document.createElement("div"); p.className = "p";
    p.style.left = (Math.random() * 100) + "%";
    if (kind === "win") { p.style.background = cols[i % cols.length]; p.style.borderRadius = i % 3 === 0 ? "50%" : "2px"; }
    else p.textContent = "💧";
    f.appendChild(p);
    var dist = (f.offsetHeight || 520) + 40, rot = kind === "win" ? 760 : 0;
    var a = anim(p, [{transform: "translateY(0) rotate(0deg)", opacity: 1}, {transform: "translateY(" + dist + "px) rotate(" + rot + "deg)", opacity: .9}], {duration: 1100 + Math.random() * 1100, delay: Math.random() * 450, easing: "linear", fill: "both"});
    if (!a) p.style.display = "none";
  }
  // papan: getar saat kalah, denyut sel pemenang
  if (kind === "lose") anim(g, [{transform: "translateX(0)"}, {transform: "translateX(-10px)"}, {transform: "translateX(9px)"}, {transform: "translateX(-7px)"}, {transform: "translateX(6px)"}, {transform: "translateX(0)"}], {duration: 600, easing: "ease-in-out"});
  for (var k = 0; k < wl.length; k++) anim(cells[wl[k]], [{transform: "scale(1)"}, {transform: "scale(1.12)"}, {transform: "scale(1)"}], {duration: 550, iterations: 4, easing: "ease-in-out"});
  haptic(kind);
  animT = setTimeout(stopAnim, ANIM_MS);
}
for (var i = 0; i < 9; i++) {
  (function (i) {
    var c = document.createElement("button"); c.className = "c"; c.addEventListener("pointerdown", function (ev) { ev.preventDefault(); play(i); });
    g.appendChild(c); cells.push(c);
  })(i);
}
// garis kemenangan (SVG) di atas papan
function drawLine() {
  var old = g.querySelector(".wl"), key = wl.length === 3 ? wl.join(",") : "";
  if (key === lineKey && (!key || old)) return;
  lineKey = key;
  if (old) g.removeChild(old);
  if (!key) return;
  var a = cells[wl[0]], z = cells[wl[2]];
  var ax = a.offsetLeft + a.offsetWidth / 2, ay = a.offsetTop + a.offsetHeight / 2, zx = z.offsetLeft + z.offsetWidth / 2, zy = z.offsetTop + z.offsetHeight / 2;
  var dx = zx - ax, dy = zy - ay, ln = Math.sqrt(dx * dx + dy * dy) || 1, ex = dx / ln * 14, ey = dy / ln * 14;
  var NS = "http://www.w3.org/2000/svg", s = document.createElementNS(NS, "svg"), l = document.createElementNS(NS, "line");
  s.setAttribute("class", "wl"); s.style.color = b[wl[0]] === "X" ? "var(--x)" : "var(--o)";
  l.setAttribute("x1", ax - ex); l.setAttribute("y1", ay - ey); l.setAttribute("x2", zx + ex); l.setAttribute("y2", zy + ey);
  l.setAttribute("stroke", "currentColor");
  s.appendChild(l); g.appendChild(s);
  var tl = ln + 28;
  anim(l, [{strokeDasharray: tl + "px", strokeDashoffset: tl + "px"}, {strokeDasharray: tl + "px", strokeDashoffset: "0px"}], {duration: 450, delay: 200, easing: "ease-out", fill: "backwards"});
}
function paint(msg, cls, canPlay) {
  for (var i = 0; i < 9; i++) {
    var c = cells[i], v = b[i];
    c.className = "c" + (v === "X" ? " x" : v === "O" ? " o" : "") + (wl.indexOf(i) >= 0 ? " w" : "");
    c.disabled = !canPlay || !!v;
    if (shown[i] !== v) {
      c.innerHTML = v ? markSVG(v) : "";
      if (v && !shown[i]) {   // tanda baru: digambar bertahap + membal
        var ps = c.querySelectorAll("path,circle");
        for (var k = 0; k < ps.length; k++) anim(ps[k], [{strokeDasharray: "1", strokeDashoffset: 1}, {strokeDasharray: "1", strokeDashoffset: 0}], {duration: 240, delay: k * 130, easing: "ease-out", fill: "backwards"});
        anim(c.firstChild, [{transform: "scale(.6)", opacity: .2}, {transform: "scale(1)", opacity: 1}], {duration: 260, easing: "cubic-bezier(.2,1.6,.4,1)"});
      }
      shown[i] = v;
    }
  }
  drawLine();
  $("sx").textContent = sc.x; $("so").textContent = sc.o; $("sd").textContent = sc.d;
  st.className = "st" + (cls ? " " + cls : ""); st.textContent = msg;
}
// ---- lawan bot
function renderBot(res) {
  wl = res ? res.l : [];
  var m = "Giliran kamu", cls = "";
  if (over) {
    if (res.w === "X") { m = "Kamu menang! 🎉"; cls = "win"; }
    else if (res.w === "O") { m = "Bot menang 🤖"; cls = "lose"; }
    else m = "Seri 🤝";
  } else if (busy) m = "Bot berpikir...";
  paint(m, cls, !over && !busy);
}
var nextT = null;
function finish(r) {
  over = true; bsc[r.w === "X" ? "x" : r.w === "O" ? "o" : "d"]++; sc = bsc; save(); renderBot(r);
  playAnim(r.w === "X" ? "win" : r.w === "O" ? "lose" : "draw");
  clearTimeout(nextT); nextT = setTimeout(function () { if (mode === "bot" && over) botRound(); }, ANIM_MS);   // setelah animasi, lanjut ronde berikutnya
}
function botPlay(i) {
  if (over || busy || b[i]) return;
  hap(); b[i] = "X";
  var r = win(b);
  if (r) return finish(r);
  busy = true; renderBot();
  setTimeout(function () {
    b[botMove()] = "O"; busy = false;
    var r2 = win(b);
    if (r2) finish(r2); else renderBot();
  }, 150);
}
function botRound() { clearTimeout(nextT); stopAnim(); b = ["", "", "", "", "", "", "", "", ""]; over = false; busy = false; renderBot(); }
function sides(l, r) { $("pl1").style.setProperty("--ac", l); $("pl2").style.setProperty("--ac", r); }
function showDiff() {
  for (var k = 1; k <= 4; k++) { var r = bscs[k]; $("rc" + k).textContent = (r.x + r.o + r.d) ? "Rekor kamu: " + r.x + " menang \u00b7 " + r.d + " seri \u00b7 " + r.o + " kalah" : "Belum pernah dimainkan"; }
  show("df");
}
function startBot(lv) {
  LV = lv || LV; bsc = bscs[LV];
  stopPoll(); mode = "bot"; net = null; sc = bsc; sides("var(--x)", "var(--o)");
  $("mode").textContent = "Lawan Bot \u00b7 " + NAMES[LV]; $("vs").textContent = ""; $("l1").textContent = "Kamu"; $("l2").textContent = "Bot";
  show("gm"); botRound();
}
// ---- lawan teman
function api(path, body) {
  var o = {headers: {"X-Init-Data": INIT}};
  if (body) { o.method = "POST"; o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(body); }
  return fetch(path, o).then(function (r) { return r.json().then(function (j) { j.__ok = r.ok; return j; }); });
}
function stopPoll() { if (timer) { clearInterval(timer); timer = null; } }
function renderNet() {
  if (!net) return;
  var N = (hold && Date.now() < hold.until) ? hold.net : net;
  b = N.b; wl = N.line || []; over = N.over;
  var me = N.me;
  sc = me === "X" ? N.score : {x: N.score.o, o: N.score.x, d: N.score.d};
  // skor selalu ditampilkan: sisi kiri = kamu, kanan = lawan; warna mengikuti tanda masing-masing
  var mine = me === "X" ? N.score.x : N.score.o, theirs = me === "X" ? N.score.o : N.score.x;
  sides(me === "X" ? "var(--x)" : "var(--o)", me === "X" ? "var(--o)" : "var(--x)");
  $("l1").textContent = "Kamu"; $("l2").textContent = N.opp;
  $("vs").textContent = "Kamu (" + me + ") lawan " + N.opp + " (" + (me === "X" ? "O" : "X") + ")";
  var m, cls = "", can = false;
  if (!N.joined) m = "Menunggu " + N.opp + " bergabung...";
  else if (over) {
    if (N.res === "D") m = "Seri 🤝";
    else if (N.res === me) { m = "Kamu menang! 🎉"; cls = "win"; }
    else { m = N.opp + " menang"; cls = "lose"; }
  } else if (N.turn === me) { m = "Giliran kamu"; can = true; }
  else m = "Giliran " + N.opp;
  paint(m, cls, can);
  $("sx").textContent = mine; $("so").textContent = theirs; $("sd").textContent = N.score.d;
}
function gotNet(j) {
  if (!j || j.__ok === false) {
    stopPoll();
    st.className = "st lose"; st.textContent = (j && j.error) || "Terhubung gagal, coba lagi.";
    for (var i = 0; i < 9; i++) cells[i].disabled = true;
    return;
  }
  net = j; gid = j.id;
  if (j.joined) {
    if (j.over && j.rid !== animRid) {   // ronde baru selesai: tahan papan akhir sambil memutar animasi, setelah itu lanjut ronde
      animRid = j.rid; hold = {net: j, until: Date.now() + ANIM_MS};
      renderNet();   // papan akhir + garis pemenang tampil dulu, baru animasi (sel pemenang sudah dikenal)
      playAnim(j.res === "D" ? "draw" : j.res === j.me ? "win" : "lose");
      setTimeout(function () { hold = null; renderNet(); }, ANIM_MS + 40);
      return;
    } else if (!j.over && j.last && j.last.rid !== animRid) {   // ronde sudah selesai sebelum sempat terlihat: animasinya tetap diputar
      animRid = j.last.rid;
      playAnim(j.last.res === "D" ? "draw" : j.last.res === j.me ? "win" : "lose");
    }
  }
  renderNet();
}
function poll() { if (mode === "net" && gid) api("api/tttstate?g=" + gid).then(gotNet, function () {}); }
function resetBoardView() { shown = ["", "", "", "", "", "", "", "", ""]; lineKey = ""; for (var i = 0; i < 9; i++) cells[i].innerHTML = ""; var o = g.querySelector(".wl"); if (o) g.removeChild(o); }
function openNet(id) {
  stopPoll(); animRid = -1; hold = null; stopAnim(); mode = "net"; gid = id; net = null; b = ["", "", "", "", "", "", "", "", ""]; over = false; wl = [];
  resetBoardView();
  $("mode").textContent = "Lawan Teman"; $("vs").textContent = ""; show("gm");
  paint("Memuat...", "", false);
  api("api/tttstate?g=" + id).then(gotNet, function () { paint("Gagal terhubung.", "lose", false); });
  timer = setInterval(poll, 1500);
}
function friends() {
  stopPoll(); mode = "menu"; show("fr");
  var fl = $("fl"); fl.innerHTML = "<div class='sec'>Memuat...</div>";
  api("api/tttplayers").then(function (j) {
    if (j.__ok === false) { fl.innerHTML = ""; var d = document.createElement("div"); d.className = "sec"; d.textContent = j.error || "Gagal memuat."; fl.appendChild(d); return; }
    fl.innerHTML = "";
    function head(t) { var d = document.createElement("div"); d.className = "sec"; d.textContent = t; fl.appendChild(d); }
    function row(name, extra, label, fn) {
      var r = document.createElement("div"); r.className = "row";
      var av = document.createElement("div"); av.className = "av"; av.textContent = (name || "?").charAt(0).toUpperCase(); r.appendChild(av);
      var s = document.createElement("span"); s.textContent = name; r.appendChild(s);
      if (extra) { var e = document.createElement("i"); e.textContent = extra; r.appendChild(e); }
      var bt = document.createElement("button"); bt.textContent = label; bt.addEventListener("click", fn); r.appendChild(bt);
      fl.appendChild(r);
    }
    if (j.games.length) {
      head("PERMAINAN BERJALAN");
      j.games.forEach(function (x) { row(x.opp, !x.joined ? "menunggu" : x.mine ? "giliranmu" : "", "Lanjut", function () { openNet(x.id); }); });
    }
    head("TEMAN TERDAFTAR");
    if (!j.players.length) head("Belum ada teman lain yang terdaftar di bot.");
    j.players.forEach(function (p) {
      row(p.name, "", "Undang", function () {
        api("api/tttinvite", {to: p.id}).then(function (r) {
          if (r.__ok === false) { alert(r.error || "Gagal mengundang."); return; }
          openNet(r.id);
        });
      });
    });
  }, function () { fl.textContent = "Gagal memuat daftar teman."; });
}
function play(i) {
  if (mode === "bot") return botPlay(i);
  if (mode === "net" && net && net.joined && !net.over && net.turn === net.me && !net.b[i]) {
    hap(); net.b[i] = net.me; net.turn = net.me === "X" ? "O" : "X"; renderNet();
    api("api/tttmove", {g: gid, c: i}).then(gotNet, function () {});
  }
}
$("mb").addEventListener("click", showDiff);
$("db").addEventListener("click", function () { show("menu"); });
var dfb = document.querySelectorAll("#df .big");
for (var z = 0; z < dfb.length; z++) dfb[z].addEventListener("click", function () { hap(); startBot(+this.getAttribute("data-lv")); });
$("mf").addEventListener("click", friends);
$("fb").addEventListener("click", function () { show("menu"); });
$("gb").addEventListener("click", function () { stopPoll(); stopAnim(); clearTimeout(nextT); hold = null; mode = "menu"; show("menu"); });
$("rr").addEventListener("click", function () {
  if (mode === "bot") botRound(); else if (mode === "net") api("api/tttround", {g: gid}).then(gotNet, function () {});
});
$("rs").addEventListener("click", function () {
  if (mode === "bot") { bscs[LV] = blank(); bsc = bscs[LV]; sc = bsc; save(); botRound(); }
  else if (mode === "net") api("api/tttreset", {g: gid}).then(gotNet, function () {});
});
var q = /[?&]g=([0-9a-f]{8})/.exec(location.search);
if (q) openNet(q[1]); else show("menu");
})();
