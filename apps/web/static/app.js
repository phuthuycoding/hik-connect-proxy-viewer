// SPA xem cam: login, danh sách kênh, player HLS từng ô với điều khiển, tự nối lại khi app quay lại từ nền.
(() => {
  const $ = (id) => document.getElementById(id);
  const loginView = $("login");
  const appView = $("app");
  const grid = $("grid");
  const players = [];
  const LIVE_BEHIND_SECONDS = 15;   // trễ hơn mức này thì báo "Trễ" và nút LIVE có tác dụng
  const STALL_SECONDS = 12;         // video không nhích trong khoảng này thì nối lại

  const icons = {
    play: '<svg class="i" viewBox="0 0 24 24"><path d="M7 5v14l11-7z" fill="currentColor" stroke="none"/></svg>',
    pause: '<svg class="i" viewBox="0 0 24 24"><path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor" stroke="none"/></svg>',
    live: '<svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/><path d="M5 12a7 7 0 0 1 7-7M19 12a7 7 0 0 1-7 7"/></svg>',
    camera: '<svg class="i" viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>',
    pip: '<svg class="i" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><rect x="11" y="11" width="8" height="6" rx="1" fill="currentColor" stroke="none"/></svg>',
    full: '<svg class="i" viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
    reload: '<svg class="i" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/></svg>',
  };

  // ---------- API ----------
  async function api(path, options) {
    const res = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options });
    if (res.status === 401) throw new Error("unauthorized");
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return res.json();
  }

  function toast(text, ms = 2200) {
    const el = document.createElement("div");
    el.className = "toast"; el.textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms);
  }

  // ---------- Views ----------
  function showLogin(message) {
    stopPlayers();
    closeToday();
    appView.hidden = true;
    loginView.hidden = false;
    $("err").textContent = message || "";
    $("password").focus();
  }

  async function showApp() {
    loginView.hidden = true;
    appView.hidden = false;
    await loadCameras();
    checkToday();
  }

  async function loadCameras() {
    const btn = $("refreshBtn");
    btn.classList.add("spin");
    try {
      const data = await api("/api/cameras");
      renderCameras(data.channels || []);
    } catch (err) {
      if (err.message === "unauthorized") return showLogin();
      grid.dataset.count = "1";
      grid.innerHTML = '<div class="empty">Không lấy được danh sách camera.<br>Bấm nút tải lại ở góc trên.</div>';
    } finally {
      btn.classList.remove("spin");
    }
  }

  function stopPlayers() {
    for (const p of players) p.destroy();
    players.length = 0;
    grid.innerHTML = "";
  }

  function renderCameras(cameras) {
    stopPlayers();
    $("count").textContent = cameras.length ? `${cameras.length} cam` : "";
    grid.dataset.count = String(Math.min(Math.max(cameras.length, 1), 9));
    if (cameras.length === 0) {
      grid.innerHTML = '<div class="empty">Tài khoản chưa được xem kênh nào, hoặc đang dò kênh.<br>Thử tải lại sau một phút.</div>';
      return;
    }
    for (const cam of cameras) players.push(createTile(cam));
  }

  // ---------- Tile / player ----------
  function createTile(cam) {
    const tile = document.createElement("div");
    tile.className = "tile";
    tile.innerHTML = `
      <video muted autoplay playsinline></video>
      <div class="head"><span class="name"></span><span class="badge"></span></div>
      <div class="overlay"><div><div class="spinner"></div>Đang kết nối...</div></div>
      <div class="controls">
        <button class="ctl" data-act="toggle" title="Tạm dừng / phát">${icons.pause}</button>
        <button class="ctl" data-act="live" title="Về thời gian thực">${icons.live}</button>
        <span class="spacer"></span>
        <button class="ctl" data-act="snap" title="Chụp ảnh">${icons.camera}</button>
        <button class="ctl" data-act="pip" title="Hình trong hình">${icons.pip}</button>
        <button class="ctl" data-act="full" title="Toàn màn hình">${icons.full}</button>
      </div>`;
    tile.querySelector(".name").textContent = cam.name;
    grid.appendChild(tile);

    const video = tile.querySelector("video");
    const badge = tile.querySelector(".badge");
    const overlay = tile.querySelector(".overlay");
    const src = `/hls/ch${cam.channel}/index.m3u8`;
    const state = { hls: null, retry: null, watchdog: null, lastTime: 0, lastProgress: Date.now(), userPaused: false };

    const setOverlay = (html) => { overlay.innerHTML = html; overlay.hidden = !html; overlay.classList.toggle("paused", html === "paused"); if (html === "paused") overlay.innerHTML = icons.play; };
    const connecting = (text) => setOverlay(`<div><div class="spinner"></div>${text}</div>`);

    function latency() {
      if (state.hls && Number.isFinite(state.hls.latency)) return state.hls.latency;
      const b = video.buffered;
      return b.length ? Math.max(0, b.end(b.length - 1) - video.currentTime) : 0;
    }

    function updateBadge() {
      if (video.paused || video.readyState < 3) { badge.textContent = ""; badge.className = "badge"; return; }
      const behind = latency() > LIVE_BEHIND_SECONDS;
      badge.textContent = behind ? "TRỄ" : "LIVE";
      badge.className = "badge " + (behind ? "behind" : "live");
    }

    function goLive() {
      if (state.hls) {
        const pos = state.hls.liveSyncPosition;
        if (Number.isFinite(pos)) video.currentTime = pos;
      } else if (video.seekable.length) {
        video.currentTime = video.seekable.end(video.seekable.length - 1);
      }
      video.play().catch(() => {});
    }

    function retryLater(text) {
      connecting(text);
      clearTimeout(state.retry);
      state.retry = setTimeout(start, 3000);
    }

    function start() {
      clearTimeout(state.retry);
      if (state.hls) { state.hls.destroy(); state.hls = null; }
      connecting("Đang kết nối đầu ghi...");
      state.lastProgress = Date.now();
      if (window.Hls && Hls.isSupported()) {
        const hls = new Hls({ liveSyncDurationCount: 3, liveMaxLatencyDurationCount: 8, maxBufferLength: 20 });
        state.hls = hls;
        hls.loadSource(src);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => { if (!state.userPaused) video.play().catch(() => {}); });
        hls.on(Hls.Events.ERROR, (_, data) => {
          if (!data.fatal) return;
          if (data.response && data.response.code === 401) { showLogin("Phiên hết hạn, đăng nhập lại."); return; }
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR) { hls.recoverMediaError(); return; }
          // Kênh chưa có stream (đầu ghi đang login) hoặc mạng rớt: thử lại sau 3 giây
          retryLater("Đang kết nối đầu ghi, thử lại...");
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = src;  // Safari iOS phát HLS native
        video.addEventListener("error", () => retryLater("Đang kết nối đầu ghi, thử lại..."), { once: true });
        if (!state.userPaused) video.play().catch(() => {});
      } else {
        setOverlay("<div>Trình duyệt không hỗ trợ HLS</div>");
      }
    }

    // Video không nhích trong STALL_SECONDS dù đang phát: nối lại (thường gặp sau khi máy ngủ)
    state.watchdog = setInterval(() => {
      if (video.paused || document.hidden) { state.lastProgress = Date.now(); return; }
      if (video.currentTime !== state.lastTime) { state.lastTime = video.currentTime; state.lastProgress = Date.now(); }
      else if (Date.now() - state.lastProgress > STALL_SECONDS * 1000) { state.lastProgress = Date.now(); start(); }
      updateBadge();
    }, 1000);

    video.addEventListener("playing", () => { setOverlay(""); updateBadge(); });
    video.addEventListener("waiting", () => { if (!video.paused) connecting("Đang tải..."); });
    video.addEventListener("pause", () => { if (state.userPaused) setOverlay("paused"); updateBadge(); });

    const actions = {
      toggle() {
        if (video.paused) { state.userPaused = false; setOverlay(""); goLive(); }
        else { state.userPaused = true; video.pause(); }
        tile.querySelector('[data-act="toggle"]').innerHTML = video.paused ? icons.play : icons.pause;
      },
      live() { state.userPaused = false; goLive(); toast("Về thời gian thực"); },
      snap() {
        const c = document.createElement("canvas");
        c.width = video.videoWidth; c.height = video.videoHeight;
        if (!c.width) return toast("Chưa có hình để chụp");
        c.getContext("2d").drawImage(video, 0, 0);
        c.toBlob((blob) => {
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `${cam.name.replace(/\s+/g, "_")}_${new Date().toISOString().replace(/[:.]/g, "-")}.png`;
          a.click();
          setTimeout(() => URL.revokeObjectURL(a.href), 5000);
        }, "image/png");
      },
      async pip() {
        try {
          if (document.pictureInPictureElement) await document.exitPictureInPicture();
          else if (video.requestPictureInPicture) await video.requestPictureInPicture();
          else if (video.webkitSetPresentationMode) video.webkitSetPresentationMode("picture-in-picture");
          else toast("Trình duyệt không hỗ trợ hình trong hình");
        } catch (err) { toast("Không mở được hình trong hình"); }
      },
      full() {
        if (document.fullscreenElement) document.exitFullscreen();
        else if (tile.requestFullscreen) tile.requestFullscreen();
        else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();  // iOS Safari chỉ cho full thẻ video
      },
    };
    tile.querySelector(".controls").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (btn) { e.stopPropagation(); actions[btn.dataset.act](); }
    });
    // Chạm một lần trên điện thoại: hiện/ẩn thanh điều khiển; nhấp đúp: toàn màn hình
    tile.addEventListener("click", (e) => { if (!e.target.closest(".controls")) tile.classList.toggle("show-controls"); });
    tile.addEventListener("dblclick", (e) => { if (!e.target.closest(".controls")) actions.full(); });

    start();
    return {
      channel: cam.channel, name: cam.name,
      resume() { if (state.userPaused) return; if (state.hls) { state.hls.startLoad(); goLive(); } else start(); },
      destroy() { clearTimeout(state.retry); clearInterval(state.watchdog); if (state.hls) state.hls.destroy(); video.removeAttribute("src"); video.load(); },
    };
  }

  // ---------- Resume khi quay lại từ nền / có mạng lại ----------
  let hiddenAt = 0;
  function resumeAll() {
    if (appView.hidden) return;
    const awayMs = hiddenAt ? Date.now() - hiddenAt : 0;
    hiddenAt = 0;
    // Đi lâu (>2 phút) thì luồng phía server đã tắt: lấy lại danh sách và mở lại từ đầu
    if (awayMs > 120000) loadCameras();
    else for (const p of players) p.resume();
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) hiddenAt = Date.now();
    else resumeAll();
  });
  window.addEventListener("pageshow", (e) => { if (e.persisted) resumeAll(); });
  window.addEventListener("online", resumeAll);

  // ---------- Hôm nay: ảnh chụp trong ngày cho time-lapse ----------
  const todayPanel = $("today");
  let todayTimer = null;

  async function checkToday() {
    try {
      const info = await api("/api/timelapse/today");
      $("todayBtn").hidden = !info.enabled;
    } catch (_) { $("todayBtn").hidden = true; }
  }

  function renderToday(info) {
    $("todayDate").textContent = info.date.split("-").reverse().join("/");
    const w = info.window;
    $("todaySub").textContent = w.enabled === false ? "" :
      `Chụp mỗi ${w.intervalMinutes} phút, ${w.start} đến ${w.end}` + (w.telegram ? `, gửi video Telegram lúc ${w.sendAt}` : "");
    const body = $("todayBody");
    const names = Object.fromEntries(players.map((p) => [String(p.channel), p.name]));
    const entries = Object.entries(info.channels).filter(([, slots]) => slots.length);
    if (!entries.length) {
      body.innerHTML = '<div class="empty">Chưa có ảnh nào hôm nay. Ảnh sẽ xuất hiện trong khung giờ chụp.</div>';
      return;
    }
    body.innerHTML = "";
    for (const [ch, slots] of entries) {
      const card = document.createElement("div");
      card.className = "day-cam";
      const url = (slot) => `/api/timelapse/frame/${info.date}/ch${ch}/${slot}.jpg`;
      const last = slots.length - 1;
      card.innerHTML = `
        <div class="day-cam-head"><b>${names[ch] || "Cam " + ch}</b><span class="n">${slots.length} ảnh</span></div>
        <div class="preview"><img alt=""><span class="t"></span></div>
        <input type="range" min="0" max="${last}" value="${last}">
        <div class="strip"></div>`;
      const img = card.querySelector(".preview img");
      const t = card.querySelector(".preview .t");
      const range = card.querySelector("input");
      const strip = card.querySelector(".strip");
      const show = (i) => {
        img.src = url(slots[i]); t.textContent = slots[i].replace("-", ":"); range.value = i;
        strip.querySelectorAll("img").forEach((el, k) => el.classList.toggle("on", k === i));
      };
      slots.forEach((slot, i) => {
        const th = document.createElement("img");
        th.src = url(slot); th.loading = "lazy"; th.alt = slot;
        th.addEventListener("click", () => show(i));
        strip.appendChild(th);
      });
      range.addEventListener("input", () => show(+range.value));
      show(last);
      body.appendChild(card);
      strip.scrollLeft = strip.scrollWidth;
    }
  }

  async function openToday() {
    todayPanel.hidden = false;
    $("todayBody").innerHTML = '<div class="empty">Đang tải...</div>';
    const load = async () => {
      try { renderToday(await api("/api/timelapse/today")); }
      catch (err) { if (err.message === "unauthorized") return showLogin(); $("todayBody").innerHTML = '<div class="empty">Không tải được.</div>'; }
    };
    await load();
    clearInterval(todayTimer);
    todayTimer = setInterval(load, 60000);
  }
  function closeToday() { todayPanel.hidden = true; clearInterval(todayTimer); }
  $("todayBtn").addEventListener("click", () => (todayPanel.hidden ? openToday() : closeToday()));
  $("todayClose").addEventListener("click", closeToday);

  // ---------- Top bar ----------
  $("refreshBtn").addEventListener("click", loadCameras);
  $("layoutBtn").addEventListener("click", () => {
    grid.classList.toggle("single");
    try { localStorage.setItem("layout", grid.classList.contains("single") ? "single" : "grid"); } catch (_) {}
  });
  try { if (localStorage.getItem("layout") === "single") grid.classList.add("single"); } catch (_) {}
  $("logoutBtn").addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
    showLogin();
  });

  // ---------- Login ----------
  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = $("loginBtn");
    btn.disabled = true;
    try {
      await api("/api/login", { method: "POST", headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ password: $("password").value }) });
      $("password").value = "";
      await showApp();
    } catch (err) {
      $("err").textContent = err.message === "unauthorized" ? "Sai mật khẩu, thử lại." : "Không kết nối được máy chủ.";
    } finally {
      btn.disabled = false;
    }
  });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  api("/api/session").then(showApp).catch(() => showLogin());
})();
