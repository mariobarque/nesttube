/* ═══════════════════════════════════════════════════════════════════════════
   CuratedStream — TV Client
   ═══════════════════════════════════════════════════════════════════════════ */

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  currentScreen: "home",
  selectedCategory: "All",
  currentChannelId: null,   // channel_id of last played video (for Watch-Next)
  ytPlayer: null,
  ytReady: false,
  pendingVideoId: null,
  // screen-time
  sessionLimitSeconds: 7200,
  sessionTotalSeconds: 0,
  watchAccumulator: 0,      // seconds played since last ping
  playStartTime: null,      // Date.now() when video started / resumed
  pingTimer: null,
  statusTimer: null,
};

// ── YouTube IFrame API ─────────────────────────────────────────────────────
window.onYouTubeIframeAPIReady = function () {
  state.ytReady = true;
  if (state.pendingVideoId) {
    _createPlayer(state.pendingVideoId);
    state.pendingVideoId = null;
  }
};

function _createPlayer(videoId) {
  state.ytPlayer = new YT.Player("yt-player", {
    videoId,
    width: "100%",
    height: "100%",
    playerVars: {
      autoplay: 1,
      rel: 0,               // restrict related to same channel only
      modestbranding: 1,    // minimal YouTube branding
      disablekb: 0,
      fs: 1,
      iv_load_policy: 3,    // no annotations
      playsinline: 1,
    },
    events: {
      onStateChange: _onPlayerStateChange,
      onError: _onPlayerError,
    },
  });
}

function _onPlayerStateChange(event) {
  const S = YT.PlayerState;
  if (event.data === S.PLAYING) {
    state.playStartTime = Date.now();
  } else if (event.data === S.PAUSED || event.data === S.BUFFERING) {
    _flushAccumulator();
  } else if (event.data === S.ENDED) {
    _flushAccumulator();
    // Hide the player immediately — before YouTube's end-screen renders
    document.getElementById("player-wrap").style.visibility = "hidden";
    showScreen("watchnext");
    _loadWatchNext();
  }
}

function _onPlayerError(event) {
  console.warn("YouTube player error", event.data);
  showScreen("home");
}

function _flushAccumulator() {
  if (state.playStartTime) {
    state.watchAccumulator += (Date.now() - state.playStartTime) / 1000;
    state.playStartTime = null;
  }
}

// ── Navigation ─────────────────────────────────────────────────────────────
function showScreen(name) {
  if (state.currentScreen === "player" && name !== "player") {
    // Pause and hide iframe when leaving player
    if (state.ytPlayer) {
      _flushAccumulator();
      state.ytPlayer.pauseVideo();
    }
    document.getElementById("player-wrap").style.visibility = "visible";
  }

  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(`screen-${name}`).classList.add("active");
  state.currentScreen = name;
}

// ── Video playback ─────────────────────────────────────────────────────────
function playVideo(videoId, title, channelName, channelId) {
  state.currentChannelId = channelId;
  document.getElementById("player-title").textContent = title;
  document.getElementById("player-channel").textContent = channelName;
  document.getElementById("player-wrap").style.visibility = "visible";
  showScreen("player");

  if (!state.ytReady) {
    state.pendingVideoId = videoId;
    return;
  }
  if (state.ytPlayer) {
    state.ytPlayer.loadVideoById(videoId);
  } else {
    _createPlayer(videoId);
  }
}

function exitPlayer() {
  if (state.ytPlayer) {
    _flushAccumulator();
    state.ytPlayer.stopVideo();
  }
  showScreen("home");
}

// ── API helpers ────────────────────────────────────────────────────────────
async function _get(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function _post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw Object.assign(new Error(err.detail || `POST ${path} → ${res.status}`), {
      status: res.status,
    });
  }
  return res.json();
}

// ── Session / screen-time ──────────────────────────────────────────────────
async function _refreshStatus() {
  try {
    const status = await _get("/api/session/today");
    state.sessionTotalSeconds = status.total_seconds;
    state.sessionLimitSeconds = status.limit_seconds;
    _updateTimeBadge(status);

    if (status.is_locked) {
      _showLock(status);
    } else {
      // Show 5-min warning
      if (status.remaining_seconds <= 300 && status.remaining_seconds > 0) {
        const mins = Math.ceil(status.remaining_seconds / 60);
        _showWarning(`⚠ ${mins} minute${mins !== 1 ? "s" : ""} of screen time left.`);
      } else {
        _hideWarning();
      }
    }
  } catch (e) {
    console.error("Status refresh failed:", e);
  }
}

async function _pingSession() {
  _flushAccumulator();
  const elapsed = Math.round(state.watchAccumulator);
  state.watchAccumulator = 0;

  if (elapsed > 0) {
    try {
      await _post("/api/session/ping", { elapsed_seconds: elapsed });
    } catch (e) {
      console.error("Ping failed:", e);
    }
  }
  await _refreshStatus();
}

function _updateTimeBadge(status) {
  const el = document.getElementById("time-badge");
  const rem = status.remaining_seconds;
  const h = Math.floor(rem / 3600);
  const m = Math.floor((rem % 3600) / 60);
  el.textContent = h > 0 ? `${h}h ${m}m left` : `${m}m left`;
  el.className = "time-badge" + (rem <= 300 ? " crit" : rem <= 600 ? " warn" : "");
}

function _showWarning(msg) {
  const el = document.getElementById("warning-overlay");
  document.getElementById("warning-text").textContent = msg;
  el.classList.remove("hidden");
}
function _hideWarning() {
  document.getElementById("warning-overlay").classList.add("hidden");
}

function _showLock(status) {
  const isSchedule = status.lock_reason === "schedule";
  document.getElementById("lock-title").textContent = isSchedule
    ? "Outside Viewing Hours"
    : "Screen Time Limit Reached";
  document.getElementById("lock-msg").textContent = isSchedule
    ? "Come back during allowed viewing hours."
    : "Today's screen time is up. Ask a parent to add more time.";
  document.getElementById("unlock-section").style.display = isSchedule ? "none" : "block";
  document.getElementById("unlock-error").classList.add("hidden");
  document.getElementById("unlock-input").value = "";
  document.getElementById("lock-screen").classList.remove("hidden");
}
function _hideLock() {
  document.getElementById("lock-screen").classList.add("hidden");
}

async function tryUnlock() {
  const passcode = document.getElementById("unlock-input").value;
  const errEl = document.getElementById("unlock-error");
  errEl.classList.add("hidden");
  try {
    await _post("/api/session/unlock", { passcode });
    _hideLock();
    _hideWarning();
    await _refreshStatus();
  } catch (e) {
    if (e.status === 401) {
      errEl.classList.remove("hidden");
    }
    document.getElementById("unlock-input").value = "";
  }
}

// Enter key on passcode field
document.getElementById("unlock-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") tryUnlock();
});

// ── Categories ─────────────────────────────────────────────────────────────
async function _loadCategories() {
  const bar = document.getElementById("categories-bar");
  bar.innerHTML = "";

  const [channels, categories] = await Promise.all([
    _get("/api/channels"),
    _get("/api/channels/categories"),
  ]);

  const all = ["All", ...categories];
  all.forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = "cat-chip" + (cat === state.selectedCategory ? " active" : "");
    btn.textContent = cat;
    btn.onclick = () => {
      state.selectedCategory = cat;
      document.querySelectorAll(".cat-chip").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      _loadHomeVideos();
    };
    bar.appendChild(btn);
  });

  return channels;
}

// ── Render helpers ─────────────────────────────────────────────────────────
function _fmtDuration(secs) {
  if (!secs) return "";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0)
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function _buildCard(video) {
  const card = document.createElement("div");
  card.className = "video-card";
  card.title = video.title;
  card.onclick = () =>
    playVideo(
      video.youtube_video_id,
      video.title,
      video.channel_name,
      video.channel_id
    );

  const dur = _fmtDuration(video.duration_seconds);
  card.innerHTML = `
    <div class="thumb-wrap">
      ${
        video.thumbnail_url
          ? `<img src="${video.thumbnail_url}" alt="" loading="lazy" />`
          : `<div class="thumb-placeholder">▶</div>`
      }
      ${dur ? `<span class="duration-badge">${dur}</span>` : ""}
    </div>
    <div class="card-body">
      <div class="card-title">${_esc(video.title)}</div>
      <div class="card-channel">${_esc(video.channel_name)}</div>
    </div>`;
  return card;
}

function _esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _renderGrid(containerId, videos, emptyId) {
  const grid = document.getElementById(containerId);
  const empty = emptyId ? document.getElementById(emptyId) : null;
  grid.innerHTML = "";
  if (!videos.length) {
    if (empty) empty.classList.remove("hidden");
    return;
  }
  if (empty) empty.classList.add("hidden");
  videos.forEach((v) => grid.appendChild(_buildCard(v)));
}

// ── Home ───────────────────────────────────────────────────────────────────
async function _loadHomeVideos() {
  const params = new URLSearchParams();
  if (state.selectedCategory !== "All") params.set("category", state.selectedCategory);
  params.set("limit", "60");

  const videos = await _get(`/api/videos?${params}`);
  const emptyEl = document.getElementById("home-empty");
  const grid = document.getElementById("video-grid");
  grid.innerHTML = "";

  if (!videos.length) {
    emptyEl.classList.remove("hidden");
  } else {
    emptyEl.classList.add("hidden");
    videos.forEach((v) => grid.appendChild(_buildCard(v)));
  }
}

// ── Search ─────────────────────────────────────────────────────────────────
let _searchDebounce = null;
document.getElementById("search-input").addEventListener("input", (e) => {
  clearTimeout(_searchDebounce);
  const q = e.target.value.trim();
  if (q.length < 2) {
    document.getElementById("search-grid").innerHTML = "";
    document.getElementById("search-empty").classList.add("hidden");
    return;
  }
  _searchDebounce = setTimeout(() => _runSearch(q), 320);
});

async function _runSearch(q) {
  const results = await _get(`/api/search?q=${encodeURIComponent(q)}&limit=40`);
  _renderGrid("search-grid", results, "search-empty");
}

// ── Watch-next ─────────────────────────────────────────────────────────────
async function _loadWatchNext() {
  let videos = [];

  // Prefer same channel first
  if (state.currentChannelId) {
    videos = await _get(
      `/api/videos?channel_id=${state.currentChannelId}&limit=8`
    );
  }
  // Fill up to 16 with latest across all channels
  if (videos.length < 16) {
    const more = await _get("/api/videos?limit=24");
    const seen = new Set(videos.map((v) => v.youtube_video_id));
    for (const v of more) {
      if (!seen.has(v.youtube_video_id)) {
        videos.push(v);
        seen.add(v.youtube_video_id);
      }
      if (videos.length >= 16) break;
    }
  }
  _renderGrid("watchnext-grid", videos, null);
}

// ── Boot ───────────────────────────────────────────────────────────────────
async function _boot() {
  try {
    await _loadCategories();
    await _loadHomeVideos();
    await _refreshStatus();

    // Ping every 60 s
    state.pingTimer = setInterval(_pingSession, 60_000);
    // Refresh status display every 30 s (even when not watching)
    state.statusTimer = setInterval(_refreshStatus, 30_000);
  } catch (e) {
    console.error("Boot error:", e);
  }
}

_boot();
