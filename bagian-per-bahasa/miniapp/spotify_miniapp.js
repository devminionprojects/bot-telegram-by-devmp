(function(){
var tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor("#171717"); tg.setBackgroundColor("#171717"); } catch (e) {} }
var INIT = tg ? tg.initData : "";
var base = location.pathname; if (base.slice(-1) !== "/") base += "/";
var items = [], page = 1, timer = null, seq = 0;
var $ = function (id) { return document.getElementById(id); };

if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) $("who").textContent = "Halo, " + (tg.initDataUnsafe.user.first_name || "kamu");

function status(t, ok) { $("st").textContent = t; $("dot").style.background = ok === false ? "#e5484d" : "#1db954"; if (ok === false && (curTab === "home" || curTab === "pl")) toast(t); }
var toastT = null;
function toast(t, ok) { var e = $("toast"); e.textContent = t; e.className = "toast" + (ok ? " ok" : ""); clearTimeout(toastT); toastT = setTimeout(function () { e.className = "toast hide"; }, 3200); }

function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({ "X-Init-Data": INIT }, opts.headers || {});
  return fetch(base + path, opts).then(function (r) {
    return r.json().catch(function () { return {}; }).then(function (j) {
      if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
      return j;
    });
  });
}

function ago(ts) {
  var s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return "baru saja";
  if (s < 3600) return Math.floor(s / 60) + " mnt lalu";
  if (s < 86400) return Math.floor(s / 3600) + " jam lalu";
  return Math.floor(s / 86400) + " hari lalu";
}

function row(it, subtitle, canAdd) {
  var d = document.createElement("div"); d.className = "it";
  var im = document.createElement("img"); im.className = "cv"; im.loading = "lazy"; im.alt = "";
  im.src = it.cover || BLANK;
  var tx = document.createElement("div"); tx.className = "tx";
  var t = document.createElement("div"); t.className = "t"; t.textContent = it.title;
  var a = document.createElement("div"); a.className = "a"; a.textContent = subtitle || it.artist;
  tx.appendChild(t); tx.appendChild(a); d.appendChild(im); d.appendChild(tx);
  d.addEventListener("click", function () { if (curTab === "cari") addHist(curQuery); play(it); });
  if (canAdd) {
    var b = document.createElement("button"); setAdd(b, inPl(it));
    b.setAttribute("aria-label", "Tambah ke playlist");
    b.addEventListener("click", function (e) { e.stopPropagation(); addPl(it, b); });
    d.appendChild(b);
  }
  var mo = document.createElement("button"); mo.className = "hmore"; mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); openMenu(it, e); });
  d.appendChild(mo); ctx(d, it);
  return d;
}

function uniq(list) {   // satu lagu cukup tampil sekali per orang
  var seen = {}, out = [];
  list.forEach(function (x) { var k = key(x) + "|" + (x.who || ""); if (!seen[k]) { seen[k] = 1; out.push(x); } });
  return out;
}
var psLast = {};
function ps(box) {   // HP: 4 lagu per halaman. Desktop: sebanyak yang muat di ruang kosong, tombol halaman baru muncul kalau sudah penuh
  if (!isDesk() || !box) return 4;
  if (!box.offsetParent) return psLast[box.id] || 12;
  var main = $("dmain"), mr = main.getBoundingClientRect(), br = box.getBoundingClientRect();
  var off = br.top - mr.top + main.scrollTop;
  var row = box.querySelector(".it"), rh = row ? row.offsetHeight : 82;
  var cols = Math.max(1, getComputedStyle(box).gridTemplateColumns.split(" ").length);
  var rows = Math.max(2, Math.floor((main.clientHeight - off - 80) / Math.max(40, rh)));
  return (psLast[box.id] = rows * cols);
}
function primaryArtist(it) { return String(it.artist || "").split(",")[0].trim(); }
function drawSearch() {
  var box = $("list"), has = items.length > 0, fl = sfilter;
  var showEx = !has && !curQuery;
  $("sex").className = showEx ? "" : "hide"; if (showEx) drawExplore();
  $("sfl").className = has ? "sfl" : "sfl hide";
  var chs = $("sfl").children; for (var c = 0; c < chs.length; c++) chs[c].className = "chip" + (chs[c].getAttribute("data-f") === fl ? " on" : "");
  $("sart").className = (has && fl === "artist") ? "" : "hide";
  box.className = fl === "artist" ? "list hide" : "list";
  if (has && fl === "artist") drawArtistsList(); else $("sart")._sig = "";
  drawTop(has && fl === "all");
  var P = ps(box), pages = Math.max(1, Math.ceil(items.length / P));
  if (page > pages) page = pages;
  var vis = items.slice((page - 1) * P, page * P);
  var sig = fl + "|" + curQuery + "|" + vis.map(function (x) { return key(x) + (inPl(x) ? "+" : "-"); }).join("~") + "#" + items.length;
  if (box._sig !== sig) {
    box._sig = sig; box.textContent = "";
    if (!has) {
      if (curQuery) { var e = document.createElement("div"); e.className = "empty"; e.textContent = "Tidak ada hasil untuk \u201C" + curQuery + "\u201D."; box.appendChild(e); }
    } else {
      vis.forEach(function (it) { box.appendChild(row(it, null, true)); });
    }
  }
  $("pgr").className = (has && fl !== "artist" && items.length > P) ? "pager" : "pager hide";
  $("pg").textContent = page + "/" + pages;
  $("prev").disabled = page <= 1; $("next").disabled = page >= pages;
}

var au = new Audio(); au.preload = "auto"; var cur = null, ready = false, pseq = 0, pfDone = false;
var BLANK = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
var SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
function fmt(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
var IC_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg>', IC_PAUSE = '<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4.6" height="16" rx="1.1"/><rect x="13.4" y="4" width="4.6" height="16" rx="1.1"/></svg>';
var IC_ADD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v9M7.5 12h9"/></svg>';
var IC_DONE = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#1ed760"/><path d="M7.4 12.4l3.1 3.1 6.1-6.6" fill="none" stroke="#000" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var IC_DEL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';
function setAdd(b, on) { b.className = "addb" + (on ? " done" : ""); b.innerHTML = on ? IC_DONE : IC_ADD; }
function setIc(el, on) { var k = on ? "1" : "0"; if (el.getAttribute("data-s") !== k) { el.setAttribute("data-s", k); el.innerHTML = on ? IC_PAUSE : IC_PLAY; } }
function setBtn() { setIc($("pbtn"), ready && !au.paused); npBtn(); dSync(); markPl(); try { if (navigator.mediaSession) navigator.mediaSession.playbackState = (ready && !au.paused) ? "playing" : "paused"; } catch (e) {} }
au.addEventListener("play", setBtn); au.addEventListener("pause", setBtn);
au.addEventListener("timeupdate", function () {
  if (!ready || !au.duration || !isFinite(au.duration) || seeking) return;
  $("pbar").style.width = (au.currentTime / au.duration * 100) + "%";
  if ((plMode || queue.length) && !pfDone && au.currentTime > 1) { pfDone = true; prefetchNext(); }
  if (cf > 0 && !cfDone && !repOne && !sleepEnd && au.duration > cf * 2 + 5 && au.duration - au.currentTime <= cf && (queue.length || (plMode && (plLoop || plPos < plOrder.length - 1)))) startCrossfade();
  $("ptime").textContent = fmt(au.currentTime) + " / " + fmt(au.duration);
  npTime();
});
au.addEventListener("ended", function () { if (!ready || !(au.duration > 1) || String(au.src).indexOf("data:") === 0) return; setBtn(); if (sleepEnd) { clearSleep(); toast("Timer tidur: pemutaran berhenti", true); status("Timer tidur: pemutaran berhenti."); return; } if (queue.length || plMode) { skipNext(); return; } status("Selesai. Ketuk \u25B6 untuk mengulang atau pilih lagu lain."); });
au.addEventListener("error", function () { if (ready) status("Audio tidak bisa diputar di perangkat ini.", false); });
$("pbtn").addEventListener("click", function () {
  if (!cur || !ready) return;
  if (au.paused) { if (au.ended) au.currentTime = 0; au.play().catch(function () {}); } else au.pause();
});
$("pbarw").addEventListener("click", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect();
  au.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * au.duration;
});

function showPlayer(it) {
  if (isDesk() && !deskClosed && !npVisible) { npVisible = true; $("np").className = "np"; $("np").scrollTop = 0; setRp(); }
  npTrack(it); dSync(); msSet(it); if (qOpen) drawQueue();
  $("pl").className = "player"; $("pcv").src = it.cover || BLANK; $("pt").textContent = it.title; $("pa").textContent = it.artist;
  $("pbar").style.width = "0"; $("ptime").textContent = "Memuat..."; setBtn();
}
function logPlay(it) {
  api("api/play", { method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title: it.title, artist: it.artist, cover: it.cover || "" }) }).catch(function () {});
}

function play(it, fromPl) {
  if (!fromPl && plMode) { plMode = false; updNav(); drawPl(); }
  if (!fromPl && cur && cur === it && ready) { if (au.paused) au.play().catch(function () {}); else au.pause(); return; }
  var my = ++pseq; ready = false; cur = it; pfDone = false; cfDone = false;
  au.loop = false; au.src = SILENT; au.play().catch(function () {});   // membuka kunci audio selama ketukan, supaya lagu bisa jalan sendiri setelah siap
  showPlayer(it);
  status("Memuat lagu dari server MP...");
  // tanya server: kalau file lagunya TIDAK ada di server -> "di download", kalau ada -> "memuat"
  var dlT = it.stream ? 0 : setInterval(function () {
    if (my !== pseq || ready) { clearInterval(dlT); return; }
    api("api/phase?title=" + encodeURIComponent(it.title) + "&artist=" + encodeURIComponent(it.artist)).then(function (r) {
      if (my !== pseq || ready) return;
      if (r && r.p === "unduh") { status("Lagu di download dari server MP..."); $("ptime").textContent = "Mengunduh..."; }
      else if (r && r.p === "muat") { status("Memuat lagu dari server MP..."); $("ptime").textContent = "Memuat..."; }
    }).catch(function () {});
  }, 700);
  var job = it.stream ? Promise.resolve({ url: it.stream }) :
    resolveIt(it, 2);
  job.then(function (j) {
    clearInterval(dlT);
    if (my !== pseq) return;
    it.stream = j.url; ready = true; au.src = base + j.url; au.loop = repOne; vSync();
    return au.play().then(function () {
      status("Memutar: " + it.title); plFails = 0;
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
      logPlay(it);
    }).catch(function () { status("Siap. Ketuk tombol \u25B6 untuk memutar.", true); setBtn(); logPlay(it); });
  }).catch(function (e) {
    clearInterval(dlT);
    if (my !== pseq) return;
    if (it.preview) {   // cadangan: cuplikan 30 detik dari iTunes kalau server gagal
      ready = true; au.src = it.preview;
      au.play().then(function () { status("Server gagal, memutar cuplikan 30 detik: " + it.title); logPlay(it); })
        .catch(function () { status("Siap. Ketuk tombol \u25B6 untuk memutar cuplikan.", true); });
      return;
    }
    status("Gagal: " + e.message, false); $("ptime").textContent = "";
    if (plMode) {
      plFails++;
      if (plFails < 3) setTimeout(function () { if (my === pseq && plMode) nextPl(); }, 1500);
      else { plMode = false; updNav(); drawPl(); status("Playlist berhenti: 3 lagu berturut-turut gagal diputar.", false); }
    }
  });
}

function search(q) {
  var my = ++seq; curQuery = q; status("Mencari..."); $("sex").className = "hide"; $("stop").textContent = ""; $("stop")._sig = ""; skel($("list"), 6); $("pgr").className = "pager hide";
  api("api/search?q=" + encodeURIComponent(q)).then(function (j) {
    if (my !== seq) return;
    items = j.items || []; page = 1; drawSearch();
    status(items.length ? "Tersambung. " + items.length + " lagu ditemukan." : "Tidak ada hasil.", items.length > 0);
  }).catch(function (e) { if (my === seq) status("Gagal: " + e.message, false); });
}

$("q").addEventListener("input", function () {
  clearTimeout(timer);
  var q = $("q").value.trim();
  if (!q) { items = []; page = 1; curQuery = ""; drawSearch(); status("Siap. Cari lagu di atas."); return; }
  timer = setTimeout(function () { search(q); }, 600);
});
$("q").addEventListener("keydown", function (e) {
  if (e.key === "Enter") { clearTimeout(timer); var q = $("q").value.trim(); if (q) { addHist(q); search(q); } $("q").blur(); }
});
$("prev").addEventListener("click", function () { if (page > 1) { page--; drawSearch(); } });
$("next").addEventListener("click", function () { page++; drawSearch(); });

var curTab = "home";
function showTab(name) {
  curTab = name;
  if (name !== "art") lastMain = name;
  ["cari", "global", "pl", "art"].forEach(function (n) {
    var tb = $("t-" + n); if (tb) tb.className = "tab" + (name === n ? " on" : "");
    $("p-" + n).className = name === n ? "" : "hide";
  });
  $("home").className = "home" + (name === "home" ? "" : " hide");
  document.querySelector(".card").className = "card" + (name === "home" ? " hide" : " t-" + name); closeMenu();
  var nb = document.querySelectorAll("#bnav button");
  for (var i = 0; i < nb.length; i++) nb[i].className = nb[i].getAttribute("data-t") === (name === "art" ? lastMain : name) ? "on" : "";
  window.scrollTo(0, 0); $("dmain").scrollTop = 0; $("dhome").className = "dhome" + (name === "home" ? " on" : "");
  if (name === "home") { drawHome(); loadHome(); }
  else if (name === "global") loadGlobal();
  else if (name === "pl") { status("Playlist: " + pl.length + " lagu."); drawPl(); loadPl(); }
  else if (name === "art") { /* dirender oleh openArtist */ }
  else { status("Siap. Cari lagu di atas."); drawSearch(); }
}
function loadGlobal() {
  status("Memuat lagu yang baru diputar..."); if (!$("glist").children.length) skel($("glist"), 5);
  api("api/recent").then(function (j) {
    var box = $("glist");
    var list = uniq(j.items || []);
    var sig = list.map(function (x) { return key(x) + x.who + x.ts + ago(x.ts) + (inPl(x) ? "+" : "-"); }).join("~");
    if (box._sig !== sig) {
      box._sig = sig; box.textContent = "";
      if (!list.length) { var e = document.createElement("div"); e.className = "empty"; e.textContent = "Belum ada lagu yang diputar."; box.appendChild(e); }
      list.forEach(function (it) { box.appendChild(row(it, it.artist + " \u00b7 " + it.who + " \u00b7 " + ago(it.ts), true)); });
    }
    status("Tersambung. Ketuk lagu untuk memutarnya juga.");
  }).catch(function (e) { status("Gagal: " + e.message, false); });
}
$("t-cari").addEventListener("click", function () { showTab("cari"); });
$("t-global").addEventListener("click", function () { showTab("global"); });
$("t-pl").addEventListener("click", function () { showTab("pl"); });

// ---------------------------------------------------------------- playlist (tersimpan di server, sama dengan playlist di chat bot)
var pl = [], plKeys = {}, plPage = 1, plOrder = [], plPos = -1, plMode = false, plMix = false, plLoop = false, plFails = 0;
function key(it) { return (it.title + "|" + it.artist).toLowerCase(); }
function inPl(it) { return !!plKeys[key(it)]; }
function rebuildKeys() { plKeys = {}; pl.forEach(function (x) { plKeys[key(x)] = 1; }); }
function postJ(path, obj) { return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj || {}) }); }
function resolveIt(it, tries, bg) {
  return api("api/resolve?title=" + encodeURIComponent(it.title) + "&artist=" + encodeURIComponent(it.artist) + "&ms=" + (it.ms || 0) + (bg ? "&bg=1" : "")).catch(function (e) {
    if (tries > 0 && /Pelan-pelan/.test(e.message)) return new Promise(function (r) { setTimeout(r, 2300); }).then(function () { return resolveIt(it, tries - 1, bg); });
    throw e;
  });
}
function updNav() {
  $("pprev").className = "pbtn sm" + (plMode ? "" : " hide");
  $("pnext").className = "pbtn sm" + (plMode || queue.length ? "" : " hide");
  dSync();
}
function loadPl() {
  return api("api/pl").then(function (j) { pl = j.items || []; rebuildKeys(); drawPl(); drawSearch(); }).catch(function (e) { status("Gagal memuat playlist: " + e.message, false); });
}
function addPl(it, b) {
  if (inPl(it)) { status("Sudah ada di playlist (" + pl.length + " lagu)."); return; }
  b.disabled = true;
  postJ("api/pladd", { title: it.title, artist: it.artist, ms: it.ms || 0, cover: it.cover || "" }).then(function (j) {
    if (!j.dup) {
      var n = { title: it.title, artist: it.artist, ms: it.ms || 0, cover: it.cover || "", preview: it.preview || "" };
      pl.push(n); plKeys[key(n)] = 1;
      if (plMode) {
        var idx = pl.length - 1;
        if (plMix) plOrder.splice(plPos + 1 + Math.floor(Math.random() * (plOrder.length - plPos)), 0, idx); else plOrder.push(idx);
      }
    }
    b.disabled = false; setAdd(b, true);
    status("Masuk playlist (" + pl.length + " lagu). Lagu disiapkan di latar belakang.");
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    drawPl(); toast("Ditambahkan ke Playlist Kamu", true);
  }).catch(function (e) { b.disabled = false; status("Gagal: " + e.message, false); });
}
function delPl(i) {
  postJ("api/pldel", { i: i }).then(function () {
    pl.splice(i, 1); rebuildKeys();
    if (plMode) {
      var p = plOrder.indexOf(i);
      plOrder = plOrder.filter(function (x) { return x !== i; }).map(function (x) { return x > i ? x - 1 : x; });
      if (p !== -1 && p <= plPos) plPos--;
    }
    drawPl(); drawSearch(); status("Dihapus dari playlist (" + pl.length + " lagu)."); toast("Dihapus dari Playlist Kamu", true);
  }).catch(function (e) { status("Gagal: " + e.message, false); });
}
function clearPl() {
  if (!pl.length) return;
  var go = function () {
    postJ("api/plclear", {}).then(function () {
      pl = []; rebuildKeys(); plMode = false; plPage = 1; updNav(); drawPl(); drawSearch(); status("Playlist dikosongkan.");
    }).catch(function (e) { status("Gagal: " + e.message, false); });
  };
  var msg = "Kosongkan seluruh playlist (" + pl.length + " lagu)?";
  if (tg && tg.showConfirm) tg.showConfirm(msg, function (ok) { if (ok) go(); }); else if (window.confirm(msg)) go();
}
function buildOrder(first) {
  plOrder = pl.map(function (_, i) { return i; });
  if (plMix) {
    for (var i = plOrder.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = plOrder[i]; plOrder[i] = plOrder[j]; plOrder[j] = t; }
    if (first != null) { plOrder.splice(plOrder.indexOf(first), 1); plOrder.unshift(first); }
    plPos = 0;
  } else plPos = first != null ? first : 0;
}
function startPl(mix, first) {
  if (!pl.length) { status("Playlist masih kosong. Ketuk + di hasil pencarian.", false); return; }
  plMix = mix; plMode = true; plFails = 0; buildOrder(first); playAt();
}
function playAt() {
  var it = pl[plOrder[plPos]]; if (!it) return;
  plMode = true; play(it, true); updNav(); drawPl();
}
var lastNav = 0;
function navOk() { var n = Date.now(); if (n - lastNav < 450) return false; lastNav = n; return true; }
function nextPl() {
  if (!plMode || !navOk()) return;
  var np = plPos + 1;
  if (np >= plOrder.length) {
    if (plLoop && pl.length) { buildOrder(null); np = 0; }
    else { plMode = false; updNav(); drawPl(); status("Playlist selesai."); return; }
  }
  plPos = np; playAt();
}
function prevPl() {
  if (!plMode || !navOk()) return;
  if (au.currentTime > 5) { au.currentTime = 0; return; }
  plPos = Math.max(0, plPos - 1); playAt();
}
var au2 = new Audio(); au2.preload = "auto";
function prefetchNext() {
  var a = queue[0] || (plMode ? pl[plOrder[plPos + 1]] : null), b = queue[1] || (plMode ? pl[plOrder[plPos + (queue[0] ? 1 : 2)]] : null);
  function one(it, buf) {
    if (!it) return Promise.resolve();
    var p = it.stream ? Promise.resolve({ url: it.stream }) : resolveIt(it, 4, true);
    return p.then(function (j) { it.stream = j.url; if (buf) { au2.src = base + j.url; } }).catch(function () {});
  }
  one(a, true); one(b, false);   // paralel: lagu yang sudah siap tidak menunggu lagu lain yang masih diunduh
}
function plRow(it, i) {
  var d = mk("div", "pr"); d.setAttribute("data-i", i);
  var n = mk("div", "pn"); n.innerHTML = '<span class="pnn">' + (i + 1) + '</span><svg class="pp" viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg><span class="eq"><i></i><i></i><i></i></span>';
  var tb = mk("div", "ptb"); tb.appendChild(cvImg(it, "pcv"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "t", it.title)); tx.appendChild(mk("div", "a", it.artist)); tb.appendChild(tx);
  var du = mk("div", "pd", it.ms ? fmt(it.ms / 1000) : "");
  var mo = mk("button", "hmore"); mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); openMenu(it, e); });
  d.appendChild(n); d.appendChild(tb); d.appendChild(du); d.appendChild(mo);
  d.addEventListener("click", function () { startPl(plMix, i); });
  ctx(d, it);
  return d;
}
function markPl() {
  var r = document.querySelector("#pllist .pr.on"), o = document.querySelector("#pllist .pr.pg");
  if (o && o !== r) o.classList.remove("pg");
  if (r) r.classList.toggle("pg", !!(ready && !au.paused));
  setIc($("pl-o"), !!(plMode && ready && !au.paused));
  var ar = document.querySelectorAll("#arbody .pr");   // baris lagu di halaman artis
  for (var i = 0; i < ar.length; i++) { var on = !!cur && ar[i]._k === key(cur); ar[i].classList.toggle("on", on); ar[i].classList.toggle("pg", on && !!(ready && !au.paused)); }
}
function drawPlHead() {
  var cov = $("plcov"); cov.textContent = "";
  if (pl.length >= 4) { cov.className = "plcov mos"; pl.slice(0, 4).forEach(function (it) { cov.appendChild(cvImg(it, "")); }); }
  else if (pl.length) { cov.className = "plcov"; cov.appendChild(cvImg(pl[0], "")); }
  else { cov.className = "plcov hrt"; cov.innerHTML = HEART; }
  var tot = 0; pl.forEach(function (x) { tot += (x.ms || 0); });
  var m = (ME ? ME + " \u00b7 " : "") + pl.length + " lagu";
  if (tot > 0) { var mn = Math.round(tot / 60000); m += ", " + (mn >= 60 ? Math.floor(mn / 60) + " j " + (mn % 60) + " mnt" : mn + " mnt"); }
  $("plmeta").textContent = m;
  if (pl.length) coverColor(pl[0], function (c) { $("plh").style.setProperty("--plc", c); }); else $("plh").style.setProperty("--plc", "#4a3a78");
}
function drawPl() {
  var box = $("pllist");
  var sig = pl.map(key).join("~");
  if (box._sig !== sig) {
    box._sig = sig; box.textContent = "";
    if (!pl.length) {
      var e = document.createElement("div"); e.className = "empty"; e.textContent = "Playlist masih kosong. Cari lagu, lalu ketuk + untuk menambahkan. Jumlah lagu tanpa batas."; box.appendChild(e);
    } else {
      pl.forEach(function (it, i) { box.appendChild(plRow(it, i)); });
    }
    drawPlHead();
  }
  var cp = plMode ? plOrder[plPos] : -1, rs = box.children;
  for (var q = 0; q < rs.length; q++) { var ri = rs[q].getAttribute("data-i"); if (ri !== null) rs[q].className = "pr" + (+ri === cp ? " on" : ""); }
  markPl();
  $("plpgr").className = "pager hide";
  $("pl-l").className = "pab" + repCls(); $("pl-r").className = "pab" + (plMix ? " on" : "");
  setIc($("pl-o"), plMode && ready && !au.paused);
  $("t-pl").textContent = "Playlist" + (pl.length ? " (" + pl.length + ")" : "");
  syncNp();
  drawSide();
  if (curTab === "home") drawHome();
}
$("plprev").addEventListener("click", function () { if (plPage > 1) { plPage--; drawPl(); } });
$("plnext").addEventListener("click", function () { plPage++; drawPl(); });
$("pl-o").addEventListener("click", function () { if (plMode && cur) $("pbtn").click(); else startPl(plMix, null); });
$("pl-r").addEventListener("click", function () { toggleShuf(); });
$("pl-l").addEventListener("click", function () { cycleRep(); });
$("pl-c").addEventListener("click", clearPl);
$("pprev").addEventListener("click", prevPl);
$("pnext").addEventListener("click", function () { skipNext(); });
// ---------------------------------------------------------------- kartu lagu (Now Playing) seperti Spotify: ketuk pemutar kecil untuk membukanya
var DEFACC = "rgb(90,31,58)", npSeq = 0, lyr = null, lyIdx = -2, lyOpen = false, npVisible = false;
function enc(x) { return encodeURIComponent(x); }
function setAcc(c) { $("np").style.setProperty("--acc", c); }
function npColor(url, my) {   // warna kartu diambil dari rata-rata warna cover (kalau server gambar mengizinkan), kalau tidak pakai warna bawaan
  var im = new Image(); im.crossOrigin = "anonymous";
  im.onload = function () {
    if (my !== npSeq) return;
    try {
      var c = document.createElement("canvas"); c.width = 8; c.height = 8;
      var x = c.getContext("2d"); x.drawImage(im, 0, 0, 8, 8);
      var d = x.getImageData(0, 0, 8, 8).data, r = 0, g = 0, b = 0, n = 0;
      for (var i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      var k = 0.55;
      setAcc("rgb(" + Math.round(r / n * k) + "," + Math.round(g / n * k) + "," + Math.round(b / n * k) + ")");
    } catch (e) { setAcc(DEFACC); }
  };
  im.onerror = function () { if (my === npSeq) setAcc(DEFACC); };
  im.src = url;
}
function npTrack(it) {
  vStop();
  var my = ++npSeq, cv = it.cover || "";
  $("npt").textContent = it.title; $("npa").textContent = it.artist; $("npar").textContent = (it.artist || "").split(",")[0];
  $("nphero").style.backgroundImage = cv ? "url('" + cv.split("'").join("%27") + "')" : "none";
  paintBg(cv);
  $("npai").src = cv || BLANK;
  setAcc(DEFACC); if (cv) npColor(cv, my);
  lyr = null; lyIdx = -2; renderLy();
  if (npVisible) loadLy(it, my);
  syncNp(); npBtn(); npTime();
}
function loadLy(it, my) {
  if (it.lyr !== undefined) { lyr = it.lyr; renderLy(); return; }
  api("api/lyrics?title=" + enc(it.title) + "&artist=" + enc(it.artist) + "&ms=" + (it.ms || 0)).then(function (j) {
    it.lyr = (j && j.lines && j.lines.length) ? j : null;
    if (my === npSeq) { lyr = it.lyr; renderLy(); }
  }).catch(function () {});
}
function renderLy() {
  var card = $("nplyr"), box = $("nplines"); box.textContent = ""; box.style.height = "";
  if (!lyr) { card.className = "npcard hide"; if (lfOpen) lfRender(); return; }
  card.className = "npcard" + (lyOpen ? " open" : "");
  var inn = document.createElement("div"); inn.className = "nli"; inn.style.transition = "none"; box.appendChild(inn);
  lyr.lines.forEach(function (ln) { var d = document.createElement("div"); d.className = "ll"; d.textContent = ln[1] || "\u266A"; inn.appendChild(d); });
  lyIdx = -2; paintLy(true);
  void inn.offsetHeight; inn.style.transition = "";
  if (lfOpen) lfRender();   // posisi awal tanpa animasi, perpindahan berikutnya halus
}
var scAnim = 0;
function easeIO(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
function smoothScroll(box, to, instant) {   // gulir halus dengan kurva ease-in-out (tanpa bergantung pada scroll-behavior bawaan)
  cancelAnimationFrame(scAnim);
  to = Math.max(0, Math.min(to, box.scrollHeight - box.clientHeight));
  if (instant) { box.scrollTop = to; return; }
  var from = box.scrollTop, d = to - from, t0 = performance.now(), dur = 650;
  if (Math.abs(d) < 2) return;
  (function step(now) {
    var k = Math.min(1, (now - t0) / dur);
    box.scrollTop = from + d * easeIO(k);
    if (k < 1) scAnim = requestAnimationFrame(step);
  })(t0);
}
var LY_LEAD = 0.5;   // baris berikutnya mulai bergerak sedikit sebelum dinyanyikan, seperti Spotify
function paintLy(force) {
  if (!lyr) return;
  var ct = au.currentTime || 0, idx = -1, L = lyr.lines;
  if (lyr.synced) for (var i = 0; i < L.length; i++) { if (L[i][0] <= ct + LY_LEAD) idx = i; else break; }
  if (!force && idx === lyIdx) return;
  lyIdx = idx;
  if (lfOpen) lfPaint(force);
  var box = $("nplines"), inn = box.firstChild; if (!inn) return;
  var els = inn.children, a = lyr.synced ? Math.max(idx, 0) : 0, sy = !!lyr.synced;
  for (var k = 0; k < els.length; k++) {
    var e = els[k], d = Math.abs(k - a);
    e.className = "ll" + (sy && k === idx ? " cur" : "") + (lyOpen ? "" : (k < a ? " past" : (k === a || k === a + 1 ? "" : " far")));
    if (lyOpen && sy) {   // tampilan penuh: makin jauh dari baris aktif makin pudar, kecil, dan sedikit buram
      e.style.opacity = d === 0 ? (idx < 0 ? .6 : 1) : d === 1 ? .62 : d === 2 ? .46 : d === 3 ? .34 : .24;
      e.style.transform = "scale(" + (k === idx ? 1 : .95) + ")";
      e.style.filter = d <= 1 ? "none" : "blur(" + Math.min(1.6, (d - 1) * .45).toFixed(2) + "px)";
    } else { e.style.opacity = ""; e.style.transform = ""; e.style.filter = ""; }
  }
  if (lyOpen) {   // kartu terbuka: baris aktif digulir ke sepertiga atas, semua baris terlihat
    box.style.height = ""; inn.style.transform = "";
    if (idx >= 0) smoothScroll(box, els[idx].offsetTop - box.clientHeight * 0.35, force);
  } else if (els[a]) {   // pratinjau: jendela 2 baris yang bergeser naik tiap pergantian baris
    var f = els[a], g = els[a + 1] || f;
    box.style.height = (g.offsetTop + g.offsetHeight - f.offsetTop) + "px";
    inn.style.transform = "translateY(" + (-f.offsetTop) + "px)";
  }
}
function npTime() {
  if (!npVisible || seeking) return;
  var d = au.duration, ok = ready && d && isFinite(d);
  $("npbar").style.width = ok ? (au.currentTime / d * 100) + "%" : "0";
  $("npcur").textContent = ok ? fmt(au.currentTime) : "0:00";
  $("npdur").textContent = ok ? fmt(d) : "Memuat...";
  paintLy(false);
}
function npBtn() { setIc($("npplay"), ready && !au.paused); setIc($("lfplay"), ready && !au.paused); }
function syncNp() {
  var b = $("npadd"), on = !!cur && inPl(cur);
  setAdd(b, on);
  b.setAttribute("aria-label", on ? "Hapus dari playlist" : "Tambah ke playlist");
  $("npprev").disabled = !plMode; $("npnext").disabled = !(plMode || queue.length);
  $("nploop").className = "npb" + repCls(); $("npshuf").className = "npb" + (plMix ? " on" : "");
  dSync();
}
var vEl = $("npvid"), vSeq = 0, vTimer = null, vFor = "", vTry = 0;
var cvEl = $("npcv"), cvx = cvEl.getContext("2d"), bgEl = $("npbg"), bgx = bgEl.getContext("2d"), vRaf = 0, vLast = 0;
function vidOf(it) { var m = /[?&]v=([A-Za-z0-9_-]{11})/.exec((it && it.stream) || ""); return m ? m[1] : ""; }
function vStop() {
  clearTimeout(vTimer); vSeq++; vFor = ""; vTry = 0;
  cancelAnimationFrame(vRaf); vRaf = 0;
  cvEl.className = "npvid"; $("nphero").classList.remove("hv");
  try { vEl.pause(); } catch (e) {}
  if (vEl.getAttribute("src")) { vEl.removeAttribute("src"); try { vEl.load(); } catch (e) {} }
}
function vPlayState() {
  if (!vEl.getAttribute("src")) return;
  if (au.paused || !ready) { try { vEl.pause(); } catch (e) {} vStartDraw(); return; }
  var p = vEl.play(); if (p && p.catch) p.catch(function () {});
  vStartDraw();
}
function vDrift(force) {   // sinkron video ke audio: selisih kecil dikejar lewat kecepatan putar, loncat posisi hanya kalau selisih besar
  if (!vEl.getAttribute("src") || vEl.readyState < 2 || !ready) return;
  var ct = au.currentTime || 0, d = ct - vEl.currentTime, ad = Math.abs(d);
  if (force || ad > 2.5) { try { vEl.currentTime = ct; vEl.playbackRate = 1; } catch (e) {} return; }
  if (ad > 0.3) vEl.playbackRate = d > 0 ? 1.1 : 0.9;
  else if (ad < 0.12 && vEl.playbackRate !== 1) vEl.playbackRate = 1;
}
// video digambar ke <canvas> biasa (bukan elemen <video> yang tampil), supaya tidak hilang / hitam saat halaman digulir di WebView Android
function vStartDraw() { if (!vRaf) vRaf = requestAnimationFrame(vDraw); }
function vDraw(ts) {
  vRaf = 0;
  if (!npVisible || !vEl.getAttribute("src") || vEl.readyState < 2) return;
  if (!ts || ts - vLast >= 30) {   // sekitar 30 fps cukup untuk klip lirik dan lebih hemat baterai
    vLast = ts || 0;
    var dpr = Math.min(window.devicePixelRatio || 1, 2), W = Math.round(cvEl.clientWidth * dpr), H = Math.round(cvEl.clientHeight * dpr);
    var vw = vEl.videoWidth, vh = vEl.videoHeight;
    if (W && H && vw && vh) {
      if (cvEl.width !== W || cvEl.height !== H) { cvEl.width = W; cvEl.height = H; }
      var sc = Math.min(W / vw, H / vh), dw = vw * sc, dh = vh * sc;
      cvx.clearRect(0, 0, W, H); cvx.drawImage(vEl, (W - dw) / 2, (H - dh) / 2, dw, dh);
    }
  }
  if (!vEl.paused) vRaf = requestAnimationFrame(vDraw);
}
vEl.addEventListener("seeked", vStartDraw);
function paintBg(url) {   // latar kabur dari cover: gambar kecil 16x16 diregangkan, jauh lebih ringan daripada filter blur
  bgEl._u = url || ""; bgx.clearRect(0, 0, 16, 16);
  if (!url) return;
  var im = new Image();
  im.onload = function () { if (bgEl._u !== url) return; try { bgx.drawImage(im, 0, 0, 16, 16); bgx.fillStyle = "rgba(0,0,0,.5)"; bgx.fillRect(0, 0, 16, 16); } catch (e) {} };
  im.src = url;
}
function vSync() {   // minta server menyiapkan video klip; sebelum siap, yang tampil tetap foto cover
  if (!npVisible || !cur || !cur.stream) return;
  var id = vidOf(cur); if (!id || id === vFor) return;
  vStop(); vFor = id;
  var my = vSeq;
  function poll() {
    api("api/vinfo?v=" + id).then(function (r) {
      if (my !== vSeq) return;
      if (r && r.ready && r.url) {
        vEl.muted = true; vEl.loop = false;
        vEl.onloadeddata = function () { if (my !== vSeq) return; cvEl.className = "npvid on"; $("nphero").classList.add("hv"); vDrift(true); vPlayState(); vStartDraw(); };
        vEl.onerror = function () { if (my === vSeq) { cvEl.className = "npvid"; $("nphero").classList.remove("hv"); } };
        vEl.src = base + r.url;
      } else if (r && !r.off && ++vTry < 90) {
        vTimer = setTimeout(poll, 2500);
      }
    }).catch(function () { if (my === vSeq && ++vTry < 90) vTimer = setTimeout(poll, 4000); });
  }
  poll();
}
au.addEventListener("play", vPlayState); au.addEventListener("pause", vPlayState);
au.addEventListener("seeked", function () { vDrift(true); });
au.addEventListener("timeupdate", function () { vDrift(false); });
function openNp() {
  if (!cur) return;
  npVisible = true; $("np").scrollTop = 0; $("np").className = "np"; document.body.style.overflow = "hidden"; deskClosed = false; setRp(); try { if (tg && tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (e) {}
  try { if (tg && tg.BackButton) { tg.BackButton.onClick(closeNp); tg.BackButton.show(); } } catch (e) {}
  npTrack(cur); vSync();
}
function closeNp() {
  vStop();
  npVisible = false; $("np").className = "np closed"; document.body.style.overflow = ""; deskClosed = true; closeQ(); closeLy(); setRp(); try { if (tg && tg.enableVerticalSwipes) tg.enableVerticalSwipes(); } catch (e) {}
  try { if (tg && tg.BackButton) { tg.BackButton.offClick(closeNp); tg.BackButton.hide(); } } catch (e) {}
}
$("pl").addEventListener("click", function (e) {
  var t = e.target;
  if (t.closest && (t.closest("button") || t.closest("#pbarw"))) return;
  openNp();
});
$("npx").addEventListener("click", closeNp);
$("npplay").addEventListener("click", function () { $("pbtn").click(); });
$("npprev").addEventListener("click", prevPl);
$("npnext").addEventListener("click", function () { skipNext(); });
$("nploop").addEventListener("click", function () { $("pl-l").click(); });
$("npbarw").addEventListener("click", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect();
  au.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * au.duration;
});
$("npadd").addEventListener("click", function () {
  if (!cur) return;
  if (inPl(cur)) {
    var k = key(cur);
    for (var i = 0; i < pl.length; i++) if (key(pl[i]) === k) { delPl(i); break; }
  } else addPl(cur, this);
});
$("nplyr").addEventListener("click", function () { lyOpen = !lyOpen; this.className = "npcard" + (lyOpen ? " open" : ""); paintLy(true); });
$("npshare").addEventListener("click", function () {
  if (!cur) return;
  var txt = cur.title + " - " + cur.artist;
  var link = "https://www.youtube.com/results?search_query=" + enc(txt);
  var u = "https://t.me/share/url?url=" + enc(link) + "&text=" + enc("Dengerin lagu ini: " + txt);
  try { if (tg && tg.openTelegramLink) { tg.openTelegramLink(u); return; } } catch (e) {}
  if (navigator.share) navigator.share({ title: txt, url: link }).catch(function () {}); else window.open(u, "_blank");
});
$("npmore").addEventListener("click", function () {
  if (!cur) return;
  var a = (cur.artist || "").split(",")[0].trim(); if (!a) return;
  openArtist(a);
});

setAdd($("npadd"), false);

// ---------------------------------------------------------------- Beranda ala Spotify
var recentAll = [], homeChip = "all";
var ME = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) ? String(tg.initDataUnsafe.user.first_name || tg.initDataUnsafe.user.username || "") : "";
var HEART = '<svg viewBox="0 0 24 24" fill="#fff"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>';
var GLOBE = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3.4 3.2 14.6 0 18M12 3c-3.2 3.4-3.2 14.6 0 18"/></svg>';
var DOTS = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>';
function mk(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
function cvImg(it, cls) { var im = mk("img", cls); im.alt = ""; im.loading = "lazy"; im.src = it.cover || BLANK; return im; }
function uk(list) { var sn = {}, o = []; list.forEach(function (x) { var k = key(x); if (!sn[k]) { sn[k] = 1; o.push(x); } }); return o; }
function homePlay(it) { play(it); }
function tile(name, art, fn, it) {
  var d = mk("div", "ht"); d.appendChild(art); d.appendChild(mk("span", "", name));
  if (it) {
    var pb = mk("div", "hpb"); pb.innerHTML = IC_PLAY; d.appendChild(pb); ctx(d, it);
    d.addEventListener("mouseenter", function () { if (isDesk()) coverColor(it, setHg); });
    d.addEventListener("mouseleave", function () { setHg(""); });
  }
  d.addEventListener("click", fn); return d;
}
function hcw(it) { var w = mk("div", "hcw"); w.appendChild(cvImg(it, "hcc")); var pb = mk("div", "hpb"); pb.innerHTML = IC_PLAY; w.appendChild(pb); return w; }
function artBox(cls, svg) { var d = mk("div", "hart " + cls); d.innerHTML = svg; return d; }
function togglePl(it, b) {
  if (inPl(it)) { var k = key(it); for (var i = 0; i < pl.length; i++) if (key(pl[i]) === k) { delPl(i); break; } }
  else addPl(it, b || document.createElement("button"));
}
function rowMenu(it, e) { openMenu(it, e || { clientX: 20, clientY: 20 }); }
function homeRow(it) {
  var d = mk("div", "hr");
  d.appendChild(cvImg(it, "hrc"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "hrt", it.title)); tx.appendChild(mk("div", "a", it.artist)); d.appendChild(tx);
  var ck = mk("button", "addb"); setAdd(ck, inPl(it)); ck.setAttribute("aria-label", "Playlist");
  ck.addEventListener("click", function (e) { e.stopPropagation(); togglePl(it, ck); });
  var mo = mk("button", "hmore"); mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); rowMenu(it, e); });
  d.appendChild(ck); d.appendChild(mo);
  d.addEventListener("click", function () { homePlay(it); }); ctx(d, it);
  return d;
}
function setAvatar() {
  ["hav", "dav"].forEach(function (id) {
    var box = $(id); if (!box || box._done) return; box._done = 1;
    var u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    box.textContent = (ME.charAt(0) || "\u266A").toUpperCase();
    if (u && u.photo_url) {
      var im = new Image(); im.alt = "";
      im.onload = function () { box.textContent = ""; box.appendChild(im); };
      im.src = u.photo_url;
    }
  });
}
var allOn = {}, queue = [], qOpen = false, repOne = false, seeking = false, recentLoaded = false, lastVol = 1, lfOpen = false, lfUser = 0, curQuery = "", sfilter = "all", curArtist = "", lastMain = "home", sleepAt = 0, sleepEnd = false, sleepT = null, cf = 0, cfDone = false, uvol = 1, tail = null, tailT = null;
function secHead(id, t, sc) {
  var h = mk("div", "hhead"); h.appendChild(mk("h2", "hh", t));
  var b = mk("button", "hall", allOn[id] ? "Tampilkan lebih sedikit" : "Tampilkan semua");
  b.addEventListener("click", function () { allOn[id] = !allOn[id]; sc.classList.toggle("all", !!allOn[id]); b.textContent = allOn[id] ? "Tampilkan lebih sedikit" : "Tampilkan semua"; });
  h.appendChild(b); return h;
}
function artistsOf(list) {
  var m = {}, o = [];
  list.forEach(function (x) {
    var a = String(x.artist || "").split(",")[0].trim(); if (!a) return;
    var k = a.toLowerCase();
    if (!m[k]) { m[k] = { name: a, cover: x.cover, n: 0 }; o.push(m[k]); }
    m[k].n++; if (!m[k].cover) m[k].cover = x.cover;
  });
  o.sort(function (p, q) { return q.n - p.n; });
  return o;
}
function goArtist(name) { openArtist(name); }
function drawHome() {
  setAvatar();
  var box = $("hbody"), old = box.querySelector(".hscroll.rec"), keep = old ? old.scrollLeft : 0;
  box.textContent = "";
  if (homeChip === "pod") { box.appendChild(mk("div", "empty", "Belum ada podcast di sini. Untuk sekarang khusus musik.")); return; }
  box.appendChild(mk("h1", "hgreet", greet()));
  var pool = seedShuf(uk(pl.concat(recentAll)));
  var g = mk("div", "hgrid");
  g.appendChild(tile("Playlist Kamu", artBox("g1", HEART), function () { showTab("pl"); }));
  g.appendChild(tile("Ruang Global", artBox("g2", GLOBE), function () { showTab("global"); }));
  pool.slice(0, 6).forEach(function (it) { g.appendChild(tile(it.title, cvImg(it, "hcv"), function () { homePlay(it); }, it)); });
  box.appendChild(g);
  var arts = artistsOf(pl.concat(recentAll)).slice(0, 14);
  if (arts.length) {
    var wrap = mk("div", "dsk"), sa = mk("div", "hscroll" + (allOn.art ? " all" : ""));
    arts.forEach(function (a) {
      var c = mk("div", "hc hca"); c.appendChild(hcw({ cover: a.cover })); c.appendChild(mk("div", "hn", a.name)); c.appendChild(mk("div", "hs", "Artis"));
      c.addEventListener("click", function () { goArtist(a.name); }); sa.appendChild(c);
    });
    wrap.appendChild(secHead("art", "Artis populer", sa)); wrap.appendChild(sa); box.appendChild(wrap);
  }
  if (!recentLoaded) {
    box.appendChild(mk("h2", "hh", "Baru saja didengar"));
    var ssk = mk("div", "hscroll");
    for (var q = 0; q < 6; q++) { var ck = mk("div", "hc"); ck.innerHTML = '<div class="skb hcc"></div><div class="skb skl"></div><div class="skb skl" style="width:55%"></div>'; ssk.appendChild(ck); }
    box.appendChild(ssk);
  }
  var rec = recentLoaded ? uk(recentAll).slice(0, 14) : [];
  if (rec.length) {
    var sc = mk("div", "hscroll rec" + (allOn.rec ? " all" : ""));
    rec.forEach(function (it) {
      var c = mk("div", "hc");
      c.appendChild(hcw(it));
      c.appendChild(mk("div", "hs", (it.who || "Seseorang") + " \u00b7 " + ago(it.ts)));
      c.appendChild(mk("div", "hn", it.title));
      c.appendChild(mk("div", "hs", it.artist));
      c.addEventListener("click", function () { homePlay(it); }); ctx(c, it);
      sc.appendChild(c);
    });
    box.appendChild(secHead("rec", "Baru saja didengar", sc)); box.appendChild(sc); sc.scrollLeft = keep;
  }
  var mine = recentAll.filter(function (x) { return ME && String(x.who || "").toLowerCase() === ME.toLowerCase(); });
  var often = uk(mine.length ? mine : pl).slice(0, 8);
  if (often.length) {
    box.appendChild(mk("h2", "hh", "Sering kamu putar baru-baru ini"));
    var rows = mk("div", "hrows");
    often.forEach(function (it) { rows.appendChild(homeRow(it)); });
    box.appendChild(rows);
  }
  if (!pool.length) box.appendChild(mk("div", "empty", "Belum ada lagu. Buka tab Cari untuk mulai mencari lagu."));
}
function loadHome() {
  return api("api/recent").then(function (j) { recentAll = j.items || []; recentLoaded = true; if (curTab === "home") drawHome(); }).catch(function () { recentLoaded = true; if (curTab === "home") drawHome(); });
}
var chips = document.querySelectorAll(".chip");
for (var ci = 0; ci < chips.length; ci++) chips[ci].addEventListener("click", function () {
  homeChip = this.getAttribute("data-c");
  for (var k = 0; k < chips.length; k++) chips[k].className = "chip" + (chips[k] === this ? " on" : "");
  drawHome();
});
var navBtns = document.querySelectorAll("#bnav button");
for (var ni = 0; ni < navBtns.length; ni++) navBtns[ni].addEventListener("click", function () { showTab(this.getAttribute("data-t")); });

// ---------------------------------------------------------------- layout desktop (laptop / PC)
var deskClosed = false;
var LIBI = '<svg viewBox="0 0 24 24"><path d="M5 4v16M10 4v16M15 5.5l4.5 14.5"/></svg>';
var PLUSI = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>';
function isDesk() { return !!(window.matchMedia && window.matchMedia("(min-width:1000px)").matches); }
function setRp() { document.body.classList.toggle("rp", isDesk() && (npVisible || qOpen)); }
function dSync() {
  if (!$("dbar")) return;
  var it = cur;
  $("dcv").src = it ? (it.cover || BLANK) : BLANK; $("dcv").style.visibility = it ? "visible" : "hidden";
  $("dt").textContent = it ? it.title : ""; $("da").textContent = it ? it.artist : "";
  $("dadd").style.visibility = it ? "visible" : "hidden"; if (it) setAdd($("dadd"), inPl(it));
  setIc($("dplay"), ready && !au.paused);
  $("dprev").disabled = !plMode; $("dnext").disabled = !(plMode || queue.length);
  $("dshuf").className = "dbtn" + (plMix ? " on" : "");
  $("dloop").className = "dbtn" + repCls();
  $("dpanel").className = "dbtn" + (npVisible ? " on" : "");
  $("dqueue").className = "dbtn" + (qOpen ? " on" : "");
}
function dTime() {
  if (seeking) return;
  var d = au.duration, ok = ready && d && isFinite(d);
  $("dbarfill").style.width = ok ? (au.currentTime / d * 100) + "%" : "0";
  $("dcur").textContent = ok ? fmt(au.currentTime) : "0:00";
  $("ddur").textContent = ok ? fmt(d) : "0:00";
}
function drawSide() {
  var sd = $("dside"); if (!sd) return; sd.textContent = "";
  var b1 = mk("button", "dsb"); b1.innerHTML = LIBI; b1.title = "Koleksi Kamu"; b1.addEventListener("click", function () { showTab("pl"); });
  var b2 = mk("button", "dsb"); b2.innerHTML = PLUSI; b2.title = "Cari & tambah lagu"; b2.addEventListener("click", function () { showTab("cari"); $("dq").focus(); });
  sd.appendChild(b1); sd.appendChild(b2);
  var h = mk("div", "dsh"); h.innerHTML = HEART; h.title = "Playlist Kamu"; h.addEventListener("click", function () { showTab("pl"); }); sd.appendChild(h);
  pl.slice(0, 40).forEach(function (it, i) {
    var im = cvImg(it, "dsc"); im.title = it.title + " - " + it.artist;
    im.addEventListener("click", function () { startPl(plMix, i); }); ctx(im, it); sd.appendChild(im);
  });
}
function togglePanel() {
  if (npVisible) { closeNp(); return; }
  if (!cur) return;
  deskClosed = false; npVisible = true; $("np").scrollTop = 0; $("np").className = "np"; setRp();
  npTrack(cur); vSync(); dSync();
}
$("dhome").addEventListener("click", function () { $("dq").value = ""; showTab("home"); });
$("dq").addEventListener("input", function () {
  if (curTab !== "cari") showTab("cari");
  $("q").value = this.value; $("q").dispatchEvent(new Event("input"));
});
$("dq").addEventListener("keydown", function (e) { if (e.key === "Enter") $("q").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" })); });
$("dplay").addEventListener("click", function () { $("pbtn").click(); });
$("dprev").addEventListener("click", prevPl);
$("dnext").addEventListener("click", function () { skipNext(); });
$("dshuf").addEventListener("click", function () { toggleShuf(); });
$("dloop").addEventListener("click", function () { $("pl-l").click(); });
$("dadd").addEventListener("click", function () { $("npadd").click(); });
$("dcv").addEventListener("click", togglePanel);
$("dpanel").addEventListener("click", togglePanel);
$("dbarw").addEventListener("click", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect();
  au.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * au.duration;
});
$("dvol").addEventListener("input", function () { au.volume = this.value / 100; uvol = au.volume; volIc(); });
au.addEventListener("timeupdate", dTime); au.addEventListener("durationchange", dTime);
document.addEventListener("keydown", function (e) {
  var tn = (e.target && e.target.tagName) || "";
  if (e.code === "Space" && isDesk() && cur && !/INPUT|TEXTAREA|BUTTON/.test(tn)) { e.preventDefault(); $("pbtn").click(); }
});
var rzT = null;
window.addEventListener("resize", function () { setRp(); clearTimeout(rzT); rzT = setTimeout(function () { if (curTab === "pl") drawPl(); else if (curTab === "cari") drawSearch(); }, 120); });
dSync(); drawSide();

// ---------------------------------------------------------------- warna cover, menu lagu, antrean, acak/ulang, kontrol (ala Spotify)
var colCache = {};
function hashColor(str) { var h = 0; for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return "hsl(" + (h % 360) + ",36%,27%)"; }
function coverColor(it, cb, mul) {
  var url = it.cover || "", m = mul || .55, k = (url || key(it)) + "@" + m;
  if (colCache[k]) { cb(colCache[k]); return; }
  if (!url) { colCache[k] = hashColor(k); cb(colCache[k]); return; }
  var im = new Image(); im.crossOrigin = "anonymous";
  im.onload = function () {
    var c;
    try {
      var cv = document.createElement("canvas"); cv.width = 8; cv.height = 8;
      var x = cv.getContext("2d"); x.drawImage(im, 0, 0, 8, 8);
      var d = x.getImageData(0, 0, 8, 8).data, r = 0, g = 0, b = 0, n = 0;
      for (var i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      c = "rgb(" + Math.round(r / n * m) + "," + Math.round(g / n * m) + "," + Math.round(b / n * m) + ")";
    } catch (e) { c = hashColor(k); }
    colCache[k] = c; cb(c);
  };
  im.onerror = function () { colCache[k] = hashColor(k); cb(colCache[k]); };
  im.src = url;
}
function setHg(c) { var m = $("dmain"); if (c) m.style.setProperty("--hg", c); else m.style.removeProperty("--hg"); }
function skel(box, n) {
  box.textContent = ""; box._sig = "skel";
  for (var i = 0; i < n; i++) { var r = mk("div", "sk"); r.innerHTML = '<div class="skb skc"></div><div class="skt"><div class="skb skl" style="width:62%"></div><div class="skb skl" style="width:38%"></div></div>'; box.appendChild(r); }
}
function repCls() { return (plLoop || repOne ? " on" : "") + (repOne ? " one" : ""); }
function toggleShuf() {
  if (plMode) { var ci = plOrder[plPos]; plMix = !plMix; buildOrder(ci); } else plMix = !plMix;
  drawPl(); toast("Acak: " + (plMix ? "aktif" : "mati"), true);
}
function cycleRep() {
  if (!plLoop && !repOne) plLoop = true; else if (plLoop) { plLoop = false; repOne = true; } else repOne = false;
  if (ready && au.src && String(au.src).indexOf("data:") !== 0) au.loop = repOne;
  drawPl(); toast(repOne ? "Ulang satu lagu: aktif" : plLoop ? "Ulang playlist: aktif" : "Ulang: mati", true);
}
// ---- menu lagu (klik kanan di desktop / lembar bawah di HP)
function ctx(el, it) { el.addEventListener("contextmenu", function (e) { e.preventDefault(); openMenu(it, e); }); }
function shareIt(it) {
  var txt = it.title + " - " + it.artist, link = "https://www.youtube.com/results?search_query=" + enc(txt);
  var u = "https://t.me/share/url?url=" + enc(link) + "&text=" + enc("Dengerin lagu ini: " + txt);
  try { if (tg && tg.openTelegramLink) { tg.openTelegramLink(u); return; } } catch (e) {}
  if (navigator.share) navigator.share({ title: txt, url: link }).catch(function () {}); else window.open(u, "_blank");
}
function closeMenu() { $("cm").className = "cm hide"; $("cmb").className = "cmb hide"; }
function showMenu(acts, ev, head) {
  var m = $("cm"); m.textContent = "";
  if (head) m.appendChild(head);
  acts.forEach(function (a) { var b = mk("button", "cmi" + (a[2] ? " on" : ""), a[0]); b.addEventListener("click", function (e) { e.stopPropagation(); closeMenu(); a[1](); }); m.appendChild(b); });
  $("cmb").className = "cmb"; m.className = "cm";
  if (isDesk()) {
    var r = m.getBoundingClientRect(), x = (ev && ev.clientX) || 20, y = (ev && ev.clientY) || 20;
    m.style.left = Math.max(8, Math.min(x, innerWidth - r.width - 8)) + "px";
    m.style.top = Math.max(8, Math.min(y, innerHeight - r.height - 8)) + "px";
  } else { m.style.left = ""; m.style.top = ""; }
}
function openMenu(it, ev) {
  var on = inPl(it), art = primaryArtist(it);
  var h = mk("div", "cmh"); h.appendChild(mk("img", "cmc")); h.firstChild.src = it.cover || BLANK;
  var ht = mk("div", "tx"); ht.appendChild(mk("div", "t", it.title)); ht.appendChild(mk("div", "a", it.artist)); h.appendChild(ht);
  var acts = [
    ["Putar", function () { play(it); }],
    ["Putar berikutnya", function () { playNextQ(it); }],
    ["Tambah ke antrean", function () { addQueue(it); }],
    [on ? "Hapus dari Playlist Kamu" : "Tambah ke Playlist Kamu", function () { togglePl(it); }]
  ];
  if (art) acts.push(["Buka artis", function () { openArtist(art); }]);
  acts.push(["Bagikan", function () { shareIt(it); }]);
  showMenu(acts, ev, h);
}
$("cmb").addEventListener("click", closeMenu);
$("cmb").addEventListener("contextmenu", function (e) { e.preventDefault(); closeMenu(); });
// ---- antrean
function qChanged() { updNav(); syncNp(); if (qOpen) drawQueue(); }
function addQueue(it) { queue.push(it); toast("Ditambahkan ke antrean", true); qChanged(); }
function playNextQ(it) { queue.unshift(it); toast("Akan diputar berikutnya", true); qChanged(); }
function skipNext() {
  if (queue.length) { if (!navOk()) return; var it = queue.shift(); qChanged(); play(it, true); return; }
  nextPl();
}
function qRow(it, o) {
  var d = mk("div", "qr" + (o.now ? " now" : ""));
  d.appendChild(cvImg(it, "qc"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "t", it.title)); tx.appendChild(mk("div", "a", it.artist)); d.appendChild(tx);
  if (o.qi != null) {
    var x = mk("button", "hmore"); x.innerHTML = IC_DEL; x.setAttribute("aria-label", "Hapus dari antrean");
    x.addEventListener("click", function (e) { e.stopPropagation(); queue.splice(o.qi, 1); qChanged(); });
    d.appendChild(x);
  }
  d.addEventListener("click", function () {
    if (o.now) { $("pbtn").click(); return; }
    if (o.qi != null) { queue.splice(o.qi, 1); qChanged(); play(it, true); return; }
    if (o.pp != null) { plPos = o.pp; playAt(); }
  });
  ctx(d, it);
  return d;
}
function drawQueue() {
  var b = $("qb"); b.textContent = "";
  if (cur) { b.appendChild(mk("div", "qs", "Sekarang diputar")); b.appendChild(qRow(cur, { now: true })); }
  if (queue.length) {
    var h = mk("div", "qs"); h.appendChild(mk("span", "", "Berikutnya dalam antrean"));
    var cl = mk("button", "", "Kosongkan"); cl.addEventListener("click", function () { queue = []; qChanged(); }); h.appendChild(cl); b.appendChild(h);
    queue.forEach(function (it, i) { b.appendChild(qRow(it, { qi: i })); });
  }
  var up = plMode ? plOrder.slice(plPos + 1) : [];
  if (up.length) {
    b.appendChild(mk("div", "qs", "Berikutnya dari Playlist Kamu"));
    up.slice(0, 30).forEach(function (pi, k) { if (pl[pi]) b.appendChild(qRow(pl[pi], { pp: plPos + 1 + k })); });
  }
  if (!cur) b.appendChild(mk("div", "empty", "Belum ada lagu yang diputar."));
  else if (!queue.length && !up.length) b.appendChild(mk("div", "empty", "Belum ada lagu berikutnya. Buka menu \u22EE pada lagu, lalu pilih Tambah ke antrean."));
}
function openQ() { qOpen = true; $("qp").className = "qp"; drawQueue(); setRp(); dSync(); }
function closeQ() { if (!qOpen) return; qOpen = false; $("qp").className = "qp closed"; setRp(); dSync(); }
function toggleQ() { if (qOpen) closeQ(); else openQ(); }
$("qx").addEventListener("click", closeQ);
$("dqueue").addEventListener("click", toggleQ);
$("npq").addEventListener("click", toggleQ);
$("npshuf").addEventListener("click", toggleShuf);
// ---- volume: bisukan
var VOLI = '<svg class="lp" viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 9a4 4 0 010 6"/></svg>';
var MUTI = '<svg class="lp" viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>';
function volIc() { $("dmute").innerHTML = au.volume === 0 ? MUTI : VOLI; }
$("dmute").addEventListener("click", function () {
  if (au.volume > 0) { lastVol = au.volume; au.volume = 0; $("dvol").value = 0; } else { au.volume = lastVol || 1; $("dvol").value = Math.round(au.volume * 100); }
  uvol = au.volume; volIc();
});
volIc();
// ---- bar progres bisa diseret + tooltip waktu
function dragBar(w, fillId, curId) {
  var fill = $(fillId), tm = curId ? $(curId) : null;
  function upd(e) {
    var r = w.getBoundingClientRect(), k = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    fill.style.width = (k * 100) + "%"; if (tm) tm.textContent = fmt(k * au.duration); w._r = k;
  }
  w.addEventListener("pointerdown", function (e) {
    if (!ready || !au.duration || !isFinite(au.duration)) return;
    seeking = true; w._drag = true; w.classList.add("drag");
    try { w.setPointerCapture(e.pointerId); } catch (x) {}
    upd(e);
  });
  w.addEventListener("pointermove", function (e) { if (w._drag) upd(e); });
  function end(ok) {
    if (!w._drag) return; w._drag = false; seeking = false; w.classList.remove("drag");
    if (ok && w._r != null && au.duration) au.currentTime = w._r * au.duration;
  }
  w.addEventListener("pointerup", function () { end(true); });
  w.addEventListener("pointercancel", function () { end(false); });
}
dragBar($("dbarw"), "dbarfill", "dcur"); dragBar($("npbarw"), "npbar", "npcur"); dragBar($("pbarw"), "pbar", null);
$("dbarw").addEventListener("mousemove", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect(), k = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), t = $("dtip");
  t.textContent = fmt(k * au.duration); t.style.left = (k * 100) + "%"; t.className = "btip";
});
$("dbarw").addEventListener("mouseleave", function () { $("dtip").className = "btip hide"; });
// ---- tombol media di layar kunci / notifikasi / keyboard (Media Session)
function msSet(it) {
  try { if (!navigator.mediaSession || !window.MediaMetadata) return;
    navigator.mediaSession.metadata = new MediaMetadata({ title: it.title, artist: it.artist || "", album: "Spotify", artwork: it.cover ? [{ src: it.cover, sizes: "512x512" }] : [] });
  } catch (e) {}
}
function msPos() {
  try { if (!navigator.mediaSession || !navigator.mediaSession.setPositionState || !ready || !au.duration || !isFinite(au.duration)) return;
    navigator.mediaSession.setPositionState({ duration: au.duration, playbackRate: 1, position: Math.min(au.currentTime, au.duration) });
  } catch (e) {}
}
["loadedmetadata", "play", "pause", "seeked", "durationchange"].forEach(function (n) { au.addEventListener(n, msPos); });
(function () {
  if (!navigator.mediaSession) return;
  function h(a, f) { try { navigator.mediaSession.setActionHandler(a, f); } catch (e) {} }
  h("play", function () { if (cur && ready) au.play().catch(function () {}); });
  h("pause", function () { au.pause(); });
  h("previoustrack", function () { if (plMode) prevPl(); else au.currentTime = 0; });
  h("nexttrack", function () { skipNext(); });
  h("seekto", function (d) { if (ready && d && d.seekTime != null) au.currentTime = d.seekTime; });
  h("seekbackward", function (d) { au.currentTime = Math.max(0, au.currentTime - ((d && d.seekOffset) || 10)); });
  h("seekforward", function (d) { au.currentTime = Math.min(au.duration || 1e9, au.currentTime + ((d && d.seekOffset) || 10)); });
})();
// ---- pintasan keyboard
document.addEventListener("keydown", function (e) {
  var t = e.target || {}, tn = t.tagName || "";
  var typing = /TEXTAREA|SELECT/.test(tn) || (tn === "INPUT" && t.type !== "range");
  if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); if (isDesk()) $("dq").focus(); else { showTab("cari"); $("q").focus(); } return; }
  if (e.key === "Escape") { closeMenu(); if (lfOpen) closeLy(); else if (qOpen) closeQ(); else if (typing) t.blur(); return; }
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); if (isDesk()) $("dq").focus(); else { showTab("cari"); $("q").focus(); } return; }
  if (!cur) return;
  if (e.code === "Space" && tn !== "BUTTON") { e.preventDefault(); $("pbtn").click(); }
  else if (e.key === "ArrowRight" && tn !== "INPUT" && ready) { e.preventDefault(); au.currentTime = Math.min(au.duration || 1e9, au.currentTime + 5); }
  else if (e.key === "ArrowLeft" && tn !== "INPUT" && ready) { e.preventDefault(); au.currentTime = Math.max(0, au.currentTime - 5); }
  else if (e.key === "n" || e.key === "N") skipNext();
  else if (e.key === "p" || e.key === "P") { if (plMode) prevPl(); else au.currentTime = 0; }
});
// ---- gestur di HP: geser bawah = tutup kartu, geser kiri/kanan = ganti lagu
(function () {
  var hero = $("nphero"), npEl = $("np"), sx = 0, sy = 0, dx = 0, dy = 0, ax = "", on = false;
  hero.addEventListener("touchstart", function (e) {
    if (isDesk() || e.touches.length !== 1) return;
    on = true; sx = e.touches[0].clientX; sy = e.touches[0].clientY; dx = dy = 0; ax = "";
  }, { passive: true });
  hero.addEventListener("touchmove", function (e) {
    if (!on) return;
    dx = e.touches[0].clientX - sx; dy = e.touches[0].clientY - sy;
    if (!ax && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) ax = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    if (ax === "y" && dy > 0 && npEl.scrollTop <= 0) { npEl.style.transition = "none"; npEl.style.transform = "translateY(" + dy + "px)"; if (e.cancelable) e.preventDefault(); }
    else if (ax === "x") { hero.style.transition = "none"; hero.style.transform = "translateX(" + (dx * .45) + "px)"; hero.style.opacity = String(1 - Math.min(.5, Math.abs(dx) / 420)); }
  }, { passive: false });
  function end() {
    if (!on) return; on = false;
    npEl.style.transition = ""; hero.style.transition = "transform .25s ease,opacity .25s ease";
    var close = ax === "y" && dy > 110 && npEl.scrollTop <= 0;
    npEl.style.transform = ""; hero.style.transform = ""; hero.style.opacity = "";
    if (close) closeNp();
    else if (ax === "x" && Math.abs(dx) > 70) { if (dx < 0) skipNext(); else if (plMode) prevPl(); }
  }
  hero.addEventListener("touchend", end, { passive: true });
  hero.addEventListener("touchcancel", end, { passive: true });
})();

// ---------------------------------------------------------------- sapaan, pencarian ala Spotify, halaman artis
function slotNow() { var h = new Date().getHours(); return h >= 4 && h < 11 ? 0 : h < 15 ? 1 : h < 18 ? 2 : 3; }
function greet() {
  var w = ["Selamat pagi", "Selamat siang", "Selamat sore", "Selamat malam"][slotNow()];
  return w + (ME ? ", " + ME : "");
}
function seedShuf(list) {   // urutan acak yang tetap sama selama satu waktu (pagi/siang/sore/malam) pada hari yang sama
  var d = new Date(), seed = (d.getFullYear() * 400 + d.getMonth() * 31 + d.getDate()) * 4 + slotNow();
  function rnd() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
  var a = list.slice();
  for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(rnd() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; }
  return a;
}
var hist = [];
try { hist = JSON.parse(localStorage.getItem("sp_hist") || "[]") || []; } catch (e) {}
function saveHist() { try { localStorage.setItem("sp_hist", JSON.stringify(hist)); } catch (e) {} }
function addHist(q) {
  q = String(q || "").trim(); if (!q) return;
  hist = hist.filter(function (h) { return h.toLowerCase() !== q.toLowerCase(); }); hist.unshift(q); hist = hist.slice(0, 8); saveHist();
}
function runSearch(q) { $("q").value = q; $("dq").value = q; addHist(q); sfilter = "all"; search(q); }
var GENRES = [["Pop", "pop indonesia", "#e8115b", "\uD83C\uDFA4"], ["Indie", "indie indonesia", "#1e3264", "\uD83C\uDFB8"], ["Hip-Hop", "hip hop indonesia", "#ba5d07", "\uD83C\uDFA7"],
  ["Dangdut", "dangdut", "#8d67ab", "\uD83E\uDD41"], ["Rock", "rock indonesia", "#e13300", "\uD83E\uDD18"], ["Santai", "lagu santai", "#148a08", "\u2615"],
  ["Galau", "lagu galau", "#503750", "\uD83C\uDF27"], ["Semangat", "lagu semangat", "#dc148c", "\u26A1"], ["Akustik", "akustik indonesia", "#477d95", "\uD83C\uDFBB"],
  ["Lo-fi", "lofi", "#7358ff", "\uD83C\uDF19"], ["Jazz", "jazz", "#af2896", "\uD83C\uDFB7"], ["K-Pop", "kpop", "#0d73ec", "\uD83D\uDC96"],
  ["Religi", "sholawat", "#006450", "\uD83D\uDD4C"], ["Viral TikTok", "lagu viral tiktok", "#e61e32", "\uD83D\uDD25"], ["Anak-anak", "lagu anak", "#bc5900", "\uD83C\uDF88"],
  ["Hits 2000-an", "hits 2000an indonesia", "#1e3264", "\uD83D\uDCFC"]];
function drawExplore() {
  var b = $("sex"); b.textContent = "";
  if (hist.length) {
    var h = mk("div", "xh"); h.appendChild(mk("span", "", "Pencarian terakhir"));
    var cl = mk("button", "", "Hapus semua"); cl.addEventListener("click", function () { hist = []; saveHist(); drawExplore(); }); h.appendChild(cl); b.appendChild(h);
    hist.forEach(function (q) {
      var r = mk("div", "hrw"); r.innerHTML = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
      r.appendChild(mk("span", "", q));
      var x = mk("button", "hx", "\u00D7"); x.setAttribute("aria-label", "Hapus");
      x.addEventListener("click", function (e) { e.stopPropagation(); hist = hist.filter(function (z) { return z !== q; }); saveHist(); drawExplore(); });
      r.appendChild(x); r.addEventListener("click", function () { runSearch(q); }); b.appendChild(r);
    });
  }
  b.appendChild(mk("div", "xh", "Jelajahi semua"));
  var g = mk("div", "xg");
  GENRES.forEach(function (gx) {
    var t = mk("div", "xt", gx[0]); t.style.background = gx[2]; t.appendChild(mk("span", "", gx[3]));
    t.addEventListener("click", function () { runSearch(gx[1]); }); g.appendChild(t);
  });
  b.appendChild(g);
}
function drawTop(show) {
  var t = $("stop"), sg = show ? curQuery + "|" + key(items[0]) : "";
  if (t._sig === sg) return; t._sig = sg; t.textContent = ""; if (!show) return;
  var qa = curQuery.toLowerCase(), isArt = false, src = items[0], i;
  for (i = 0; i < items.length; i++) if (primaryArtist(items[i]).toLowerCase() === qa) { isArt = true; src = items[i]; break; }
  t.appendChild(mk("div", "xh", "Hasil teratas"));
  var c = mk("div", "tpc" + (isArt ? " art" : "")); c.appendChild(cvImg(src, ""));
  c.appendChild(mk("div", "tt", isArt ? primaryArtist(src) : src.title));
  c.appendChild(mk("span", "tk", isArt ? "Artis" : "Lagu \u2022 " + src.artist));
  var pb = mk("div", "hpb"); pb.innerHTML = IC_PLAY; c.appendChild(pb);
  c.addEventListener("click", function () { addHist(curQuery); if (isArt) openArtist(primaryArtist(src)); else play(src); });
  if (!isArt) ctx(c, src);
  t.appendChild(c); t.appendChild(mk("div", "xh", "Lagu"));
}
function drawArtistsList() {
  var b = $("sart"), sg = curQuery + "#" + items.length; if (b._sig === sg) return; b._sig = sg; b.textContent = "";
  var qa = curQuery.toLowerCase(), arts = artistsOf(items);
  arts.sort(function (p, q) { return (q.name.toLowerCase() === qa) - (p.name.toLowerCase() === qa); });
  arts.forEach(function (a) {
    var r = mk("div", "arr"); r.appendChild(cvImg({ cover: a.cover }, ""));
    var tx = mk("div", "tx"); tx.appendChild(mk("b", "", a.name)); tx.appendChild(mk("small", "", "Artis")); r.appendChild(tx);
    r.addEventListener("click", function () { addHist(curQuery); openArtist(a.name); }); b.appendChild(r);
  });
}
var sfc = $("sfl").children;
for (var sci = 0; sci < sfc.length; sci++) sfc[sci].addEventListener("click", function () { sfilter = this.getAttribute("data-f"); page = 1; drawSearch(); });
$("dq").addEventListener("focus", function () { if (!this.value && curTab !== "cari") showTab("cari"); });
// ---- halaman artis
var follows = [], arCache = {};
try { follows = JSON.parse(localStorage.getItem("sp_follow") || "[]") || []; } catch (e) {}
function isFol(n) { return follows.some(function (x) { return x.toLowerCase() === n.toLowerCase(); }); }
function toggleFol(n) {
  if (isFol(n)) { follows = follows.filter(function (x) { return x.toLowerCase() !== n.toLowerCase(); }); toast("Berhenti mengikuti " + n, true); }
  else { follows.push(n); toast("Mulai mengikuti " + n, true); }
  try { localStorage.setItem("sp_follow", JSON.stringify(follows)); } catch (e) {}
}
function playList(list, start, shuf) {   // lagu pertama diputar, sisanya masuk antrean
  if (!list || !list.length) return;
  var arr = list.slice(), st = start || 0;
  if (shuf) { for (var i = arr.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = arr[i]; arr[i] = arr[j]; arr[j] = t; } st = 0; }
  var first = arr[st], rest = arr.slice(st + 1, st + 51);
  play(first); queue = rest; qChanged();
}
function openArtist(name) {
  name = String(name || "").trim(); if (!name) return;
  if (!isDesk()) closeNp();
  if (qOpen) closeQ();
  curArtist = name; showTab("art");
  renderArtist(name, arCache[name] || null);
  if (!arCache[name]) {
    api("api/search?q=" + enc(name)).then(function (j) {
      arCache[name] = j.items || [];
      if (curArtist === name && curTab === "art") renderArtist(name, arCache[name]);
    }).catch(function (e) { status("Gagal: " + e.message, false); if (curArtist === name && curTab === "art") renderArtist(name, []); });
  }
}
var SHUFI = '<svg viewBox="0 0 24 24"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>';
function arRow(it, i, src) {
  var d = mk("div", "pr"); d._k = key(it);
  var n = mk("div", "pn"); n.innerHTML = '<span class="pnn">' + (i + 1) + '</span><svg class="pp" viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg><span class="eq"><i></i><i></i><i></i></span>';
  var tb = mk("div", "ptb"); tb.appendChild(cvImg(it, "pcv"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "t", it.title)); tx.appendChild(mk("div", "a", it.artist)); tb.appendChild(tx);
  var mo = mk("button", "hmore"); mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); openMenu(it, e); });
  d.appendChild(n); d.appendChild(tb); d.appendChild(mk("div", "pd", it.ms ? fmt(it.ms / 1000) : "")); d.appendChild(mo);
  d.addEventListener("click", function () { playList(src, i); });
  ctx(d, it);
  return d;
}
function renderArtist(name, list) {
  var b = $("arbody"); b.textContent = "";
  var own = [], oth = [], nl = name.toLowerCase();
  if (list) list.forEach(function (x) { (String(x.artist || "").toLowerCase().indexOf(nl) >= 0 ? own : oth).push(x); });
  var cov = own[0] || (list && list[0]) || null;
  var h = mk("div", "plh arh");
  var bk = mk("button", "arback"); bk.innerHTML = '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>'; bk.setAttribute("aria-label", "Kembali");
  bk.addEventListener("click", function () { showTab(lastMain); }); h.appendChild(bk);
  var av = mk("div", "plcov arav"); if (cov) av.appendChild(cvImg(cov, "")); else av.className += " hrt"; h.appendChild(av);
  var pin = mk("div", "plin"); pin.appendChild(mk("div", "pltype", "Artis")); pin.appendChild(mk("h1", "pltitle", name));
  pin.appendChild(mk("div", "plmeta", list ? own.length + " lagu ditemukan" : "Memuat...")); h.appendChild(pin);
  b.appendChild(h);
  if (cov) coverColor(cov, function (c) { h.style.setProperty("--plc", c); });
  if (!list) { var sk = mk("div", ""); skel(sk, 5); b.appendChild(sk); return; }
  var main = own.length ? own : oth;
  if (!main.length) { b.appendChild(mk("div", "empty", "Tidak ada lagu untuk artis ini.")); return; }
  var act = mk("div", "plact");
  var big = mk("button", "plbig"); big.innerHTML = IC_PLAY; big.setAttribute("aria-label", "Putar"); big.addEventListener("click", function () { playList(main, 0, false); });
  var sh = mk("button", "pab"); sh.innerHTML = SHUFI; sh.setAttribute("aria-label", "Putar acak"); sh.addEventListener("click", function () { playList(main, 0, true); toast("Memutar acak", true); });
  var fb = mk("button", "fbtn" + (isFol(name) ? " on" : ""), isFol(name) ? "Mengikuti" : "Ikuti");
  fb.addEventListener("click", function () { toggleFol(name); fb.className = "fbtn" + (isFol(name) ? " on" : ""); fb.textContent = isFol(name) ? "Mengikuti" : "Ikuti"; });
  act.appendChild(big); act.appendChild(sh); act.appendChild(fb); b.appendChild(act);
  b.appendChild(mk("h2", "hh", "Populer"));
  var lst = mk("div", ""), all = main.slice(0, 20);
  all.forEach(function (it, i) { var r = arRow(it, i, main); if (i >= 5) r.classList.add("hide"); lst.appendChild(r); });
  b.appendChild(lst);
  if (all.length > 5) {
    var more = mk("button", "fbtn", "Tampilkan lainnya"); more.style.marginTop = "10px"; var open = false;
    more.addEventListener("click", function () {
      open = !open; var rs = lst.children;
      for (var i = 5; i < rs.length; i++) rs[i].classList.toggle("hide", !open);
      more.textContent = open ? "Tampilkan lebih sedikit" : "Tampilkan lainnya";
    });
    b.appendChild(more);
  }
  var sim = artistsOf(oth).filter(function (a) { return a.name.toLowerCase() !== nl; }).slice(0, 12);
  if (sim.length) {
    var ss = mk("div", "hscroll" + (allOn.arsim ? " all" : ""));
    sim.forEach(function (a) {
      var c = mk("div", "hc hca"); c.appendChild(hcw({ cover: a.cover })); c.appendChild(mk("div", "hn", a.name)); c.appendChild(mk("div", "hs", "Artis"));
      c.addEventListener("click", function () { openArtist(a.name); }); ss.appendChild(c);
    });
    b.appendChild(secHead("arsim", "Artis serupa", ss)); b.appendChild(ss);
  }
  if (oth.length) {
    var so = mk("div", "hscroll" + (allOn.arrel ? " all" : ""));
    oth.slice(0, 14).forEach(function (it) {
      var c = mk("div", "hc"); c.appendChild(hcw(it)); c.appendChild(mk("div", "hn", it.title)); c.appendChild(mk("div", "hs", it.artist));
      c.addEventListener("click", function () { homePlay(it); }); ctx(c, it); so.appendChild(c);
    });
    b.appendChild(secHead("arrel", "Lagu terkait", so)); b.appendChild(so);
  }
  markPl();
}
// ---------------------------------------------------------------- lirik layar penuh
function lfScroll(el, instant) {
  var box = $("lfb"), r = el.getBoundingClientRect(), br = box.getBoundingClientRect();
  smoothScroll(box, box.scrollTop + (r.top - br.top) - box.clientHeight * .3, instant);
}
function lfRender() {
  var inn = $("lfi"); inn.textContent = "";
  $("lft").textContent = cur ? cur.title : ""; $("lfa").textContent = cur ? cur.artist : "";
  if (cur) coverColor(cur, function (c) { $("lyfs").style.setProperty("--lfc", c); }, .8);
  if (!lyr) { inn.appendChild(mk("div", "lfl st", "Lirik belum tersedia.")); return; }
  lyr.lines.forEach(function (ln) {
    var d = mk("div", "lfl" + (lyr.synced ? "" : " st"), ln[1] || "\u266A");
    d.addEventListener("click", function () { if (lyr.synced && ready && ln[0] != null) { au.currentTime = ln[0]; lfUser = 0; } });
    inn.appendChild(d);
  });
  lyIdx = -2; paintLy(true);
}
function lfPaint(force) {
  if (!lyr || !lyr.synced) return;
  var els = $("lfi").children, idx = lyIdx;
  for (var k = 0; k < els.length; k++) {
    var e = els[k], d = Math.abs(k - idx);
    e.className = "lfl" + (k === idx ? " cur" : "");
    e.style.opacity = idx < 0 ? .9 : d === 0 ? 1 : d === 1 ? .72 : d === 2 ? .56 : d === 3 ? .44 : .34;
    e.style.transform = "scale(" + (k === idx ? 1 : .96) + ")";
    e.style.filter = (idx < 0 || d <= 1) ? "none" : "blur(" + Math.min(1.8, (d - 1) * .5).toFixed(2) + "px)";
  }
  if (idx >= 0 && els[idx] && Date.now() - lfUser > 3500) lfScroll(els[idx], !!force);
}
function lfTime() {
  if (!lfOpen || seeking) return;
  var d = au.duration, ok = ready && d && isFinite(d);
  $("lfbar").style.width = ok ? (au.currentTime / d * 100) + "%" : "0";
  $("lfcur").textContent = ok ? fmt(au.currentTime) : "0:00"; $("lfdur").textContent = ok ? fmt(d) : "";
}
function openLy() {
  if (!cur || !lyr) return;
  lfOpen = true; lfUser = 0; $("lyfs").className = "lyfs"; lfRender(); lfTime(); setIc($("lfplay"), ready && !au.paused);
}
function closeLy() { if (!lfOpen) return; lfOpen = false; $("lyfs").className = "lyfs closed"; }
$("lfopen").addEventListener("click", function (e) { e.stopPropagation(); openLy(); });
$("lfx").addEventListener("click", closeLy);
$("lfplay").addEventListener("click", function () { $("pbtn").click(); });
$("lfprev").addEventListener("click", function () { if (plMode) prevPl(); else au.currentTime = 0; });
$("lfnext").addEventListener("click", function () { skipNext(); });
["wheel", "touchstart"].forEach(function (n) { $("lfb").addEventListener(n, function () { lfUser = Date.now(); }, { passive: true }); });
au.addEventListener("timeupdate", function () { if (lfOpen) { paintLy(false); lfTime(); } });
dragBar($("lfbarw"), "lfbar", "lfcur");
// ---------------------------------------------------------------- timer tidur, crossfade, pengaturan
try { cf = +localStorage.getItem("sp_cf") || 0; } catch (e) {}
function sleepUi() {
  var on = !!(sleepAt || sleepEnd), txt = sleepAt ? Math.max(1, Math.ceil((sleepAt - Date.now()) / 60000)) + "m" : sleepEnd ? "1" : "";
  [["dsb", "dsleep", "dbtn"], ["npsb", "npsleep", "npb"]].forEach(function (x) {
    var bd = $(x[0]); bd.textContent = txt; bd.className = on ? "bd" : "bd hide"; $(x[1]).className = x[2] + (on ? " on" : "");
  });
}
function clearSleep() { sleepAt = 0; sleepEnd = false; clearInterval(sleepT); sleepT = null; sleepUi(); }
function fadePause() {
  var v0 = au.volume, t0 = performance.now(), dur = 4000;
  (function step() {
    var k = Math.min(1, (performance.now() - t0) / dur);
    au.volume = v0 * (1 - k);
    if (k < 1) setTimeout(step, 80); else { au.pause(); au.volume = v0; }
  })();
}
function sleepTick() {
  if (sleepAt && Date.now() >= sleepAt) { clearSleep(); fadePause(); toast("Timer tidur: pemutaran dihentikan", true); status("Timer tidur: pemutaran dihentikan."); return; }
  sleepUi();
}
function setSleep(min) {
  clearSleep();
  if (min === "end") { sleepEnd = true; toast("Berhenti di akhir lagu ini", true); }
  else { sleepAt = Date.now() + min * 60000; toast("Timer tidur: " + min + " menit", true); }
  sleepT = setInterval(sleepTick, 1000); sleepUi();
}
function openSleepMenu(ev) {
  var acts = [];
  if (sleepAt || sleepEnd) acts.push(["Matikan timer", function () { clearSleep(); toast("Timer tidur dimatikan", true); }]);
  [5, 10, 15, 30, 45, 60].forEach(function (m) { acts.push([m + " menit", function () { setSleep(m); }]); });
  acts.push(["Akhir lagu ini", function () { setSleep("end"); }, sleepEnd]);
  showMenu(acts, ev, mk("div", "cmh", "Timer tidur"));
}
function openCfMenu(ev) {
  var acts = [["Mati", 0], ["3 detik", 3], ["6 detik", 6], ["9 detik", 9], ["12 detik", 12]].map(function (o) {
    return [o[0], function () { cf = o[1]; try { localStorage.setItem("sp_cf", String(cf)); } catch (e) {} toast(cf ? "Crossfade: " + cf + " detik" : "Crossfade dimatikan", true); }, cf === o[1]];
  });
  showMenu(acts, ev, mk("div", "cmh", "Crossfade"));
}
function openSettings(ev) {
  var rem = sleepAt ? Math.max(1, Math.ceil((sleepAt - Date.now()) / 60000)) + " mnt" : sleepEnd ? "akhir lagu" : "mati";
  var acts = [
    ["Timer tidur \u00B7 " + rem, function () { setTimeout(function () { openSleepMenu(ev); }, 0); }],
    ["Crossfade \u00B7 " + (cf ? cf + " detik" : "mati"), function () { setTimeout(function () { openCfMenu(ev); }, 0); }]
  ];
  if (hist.length) acts.push(["Hapus riwayat pencarian", function () { hist = []; saveHist(); if (curTab === "cari") drawSearch(); toast("Riwayat pencarian dihapus", true); }]);
  showMenu(acts, ev, mk("div", "cmh", "Pengaturan"));
}
function killTail() { clearInterval(tailT); tailT = null; if (tail) { try { tail.pause(); tail.removeAttribute("src"); } catch (e) {} tail = null; } }
function startCrossfade() {   // lagu lama tetap berbunyi di pemutar cadangan sambil memudar, lagu baru memudar masuk
  cfDone = true;
  var t = new Audio(), pos = au.currentTime, v0 = au.volume, before = pseq;
  t.src = au.src; t.volume = v0;
  t.addEventListener("loadedmetadata", function () { try { t.currentTime = pos + 0.3; } catch (e) {} }, { once: true });
  skipNext();
  if (pseq === before) return;   // tidak ada lagu berikutnya
  killTail(); tail = t; t.play().catch(function () {});
  var dur = cf * 1000, t0 = performance.now(); au.volume = 0;
  tailT = setInterval(function () {
    var k = Math.min(1, (performance.now() - t0) / dur);
    try { t.volume = Math.max(0, v0 * (1 - k)); } catch (e) {}
    au.volume = uvol * k;
    if (k >= 1) { killTail(); au.volume = uvol; }
  }, 60);
}
$("dsleep").addEventListener("click", openSleepMenu);
$("npsleep").addEventListener("click", openSleepMenu);
$("hav").addEventListener("click", openSettings);
$("dav").addEventListener("click", openSettings);
sleepUi();
loadPl();
showTab("home");
drawSearch();

})();
