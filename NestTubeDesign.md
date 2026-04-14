NestTube
Parental-Controlled YouTube Streaming System
Design Document  ·  April 13, 2026



# 1. Problem Statement

Streaming platforms — especially YouTube — offer inadequate parental controls. Recommendations and search results are driven by engagement algorithms with no mechanism for a parent to restrict content to a personally curated list of channels. Existing solutions (YouTube Kids, Family Link, Pi-hole, Circle) either block YouTube entirely or provide only broad content categories with no channel-level whitelist support. None of these solutions deliver a TV-optimised experience with a fully custom interface.

# 2. Goals

- Allow only videos from a parent-defined whitelist of YouTube channels.
- All search results and recommendations sourced exclusively from the whitelist.
- TV-first interface: delivered via HDMI from a Raspberry Pi 5.
- No YouTube account sign-in required on the TV — kids see only the curated UI.
- Configurable daily screen time limit (default: 2 hours) with automatic lockout.
- Configurable viewing schedule (e.g., weekdays 4–7 PM only).
- Parent Admin Panel accessible from any browser on the home network.
- All data, config, and secrets stored locally on the Raspberry Pi.
- YouTube API free tier is sufficient — no subscription or payment needed.

# 3. Existing Products Analysis

The table below summarises evaluated products and why none fully solves the problem.


Conclusion: No existing product provides a live, TV-optimised interface where search and recommendations are scoped to a parent-defined YouTube channel whitelist.

# 4. Proposed Solution

Build a self-hosted system running entirely on a Raspberry Pi 5. The Pi connects to the TV via HDMI and displays a fullscreen kiosk browser. A Python/FastAPI backend fetches video metadata from the YouTube Data API v3 and caches it locally in SQLite. The TV client is a plain HTML/JS web app served from localhost. A NiceGUI-based Admin Panel is accessible from the parent's phone or laptop over the home network.

# 5. YouTube Data API — Free Tier

No subscription or payment is required. A free Google Cloud project with the YouTube Data API v3 enabled provides 10,000 units per day.


# 6. Recommendation Suppression Strategy

YouTube's end-screen recommendations are suppressed through two complementary layers:

- rel=0 parameter: restricts end-screen suggestions to videos from the same channel only (secondary layer).
- modestbranding=1 + disablekb=1: removes YouTube branding and disables keyboard shortcuts.
- Primary layer — iframe hiding: the TV client listens for the YouTube IFrame Player API onStateChange ENDED event (value 0). The moment the video ends, the iframe is immediately hidden before YouTube's end screen renders. The client then displays a custom "Watch Next?" screen populated exclusively from the local curated catalog.

Video ends (ENDED event fired)
        │
        ▼
Hide < iframe > immediately
        │
        ▼
Show custom Watch-Next screen
(videos sourced from local SQLite catalog only)

# 7. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Raspberry Pi 5                          │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Python / FastAPI Backend                   │  │
│  │                                                         │  │
│  │  Routers:                                               │  │
│  │   /api/channels      — list approved channels          │  │
│  │   /api/videos        — browse catalog, by channel      │  │
│  │   /api/search        — local full-text search          │  │
│  │   /api/session       — start/ping/end screen session   │  │
│  │   /api/admin/*       — passcode-protected admin ops    │  │
│  │                                                         │  │
│  │  Background Jobs (APScheduler):                         │  │
│  │   - Channel sync (configurable, default every 1 hour)  │  │
│  │   - Screen time enforcement                             │  │
│  └───────────────┬────────────────────────────────────────┘  │
│                  │                                            │
│  ┌───────────────▼──────────┐  ┌───────────────────────────┐ │
│  │   SQLite Database        │  │  .env Secrets File         │ │
│  │                          │  │                            │ │
│  │  channels                │  │  YOUTUBE_API_KEY=...       │ │
│  │  videos                  │  │  ADMIN_PASSCODE_HASH=...   │ │
│  │  watch_sessions          │  └───────────────────────────┘ │
│  │  settings                │                                 │
│  └──────────────────────────┘                                 │
│                                                               │
│  ┌─────────────────────────┐  ┌────────────────────────────┐ │
│  │  TV Client              │  │  Admin Panel               │ │
│  │  Plain HTML/JS          │  │  NiceGUI (Python)          │ │
│  │  Served at /            │  │  Served at /admin          │ │
│  │                         │  │  Passcode protected        │ │
│  │  Screens:               │  │                            │ │
│  │  1. Home                │  │  Pages:                    │ │
│  │  2. Search              │  │  - Channel list (add/del)  │ │
│  │  3. Player              │  │  - Categories              │ │
│  │  4. Watch-Next          │  │  - Screen time limit       │ │
│  │  5. Locked (time limit) │  │  - Schedule window         │ │
│  └─────────────────────────┘  │  - Watch history           │ │
│                                │  - Force unlock            │ │
│  Chromium kiosk → localhost   └────────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────┘
                               │ HDMI
                               ▼
                            [ TV ]

Parent device ──WiFi──> http://[pi-ip]/admin
YouTube API  ──────────> Google (metadata only, outbound)
Video bytes  ──────────> Chromium direct from YouTube CDN
```

# 8. Database Schema (SQLite)

channels
  id                  INTEGER PRIMARY KEY
  youtube_channel_id  TEXT UNIQUE NOT NULL
  display_name        TEXT NOT NULL
  category            TEXT
  added_at            DATETIME DEFAULT CURRENT_TIMESTAMP

videos
  id                  INTEGER PRIMARY KEY
  youtube_video_id    TEXT UNIQUE NOT NULL
  channel_id          INTEGER REFERENCES channels(id)
  title               TEXT NOT NULL
  thumbnail_url       TEXT
  duration_seconds    INTEGER
  published_at        DATETIME
  synced_at           DATETIME DEFAULT CURRENT_TIMESTAMP

watch_sessions
  id                  INTEGER PRIMARY KEY
  started_at          DATETIME NOT NULL
  ended_at            DATETIME
  total_seconds       INTEGER DEFAULT 0
  date                DATE NOT NULL   -- for daily reset

settings
  key                 TEXT PRIMARY KEY
  value               TEXT NOT NULL
  -- Keys:
  --   screen_time_limit_minutes  (default: 120)
  --   schedule_start             (default: "00:00")
  --   schedule_end               (default: "23:59")
  --   sync_interval_minutes      (default: 60)

# 9. Screen Time Enforcement Flow

TV Client boots
        │
        ▼
GET /api/session/today
        │
   ┌────┴─────────────────┐
Under limit           At / over limit
        │                     │
   Normal use           Show lock screen
        │               (admin passcode to
   Every 60s             unlock, or wait
   ping /api/            until midnight
   session/ping          daily reset)
        │
  5-min warning
  overlay before
  limit is reached

# 10. Tech Stack


# 11. Physical Setup

The Raspberry Pi 5 is positioned near the TV with the following connections:
- HDMI cable from Pi to TV HDMI input.
- USB-C power adapter plugged into a nearby outlet.
- Ethernet to router (recommended) or Wi-Fi.

The Pi is approximately the size of a deck of cards and can be mounted behind the TV using a VESA bracket accessory. To move it to a different TV, simply unplug the power and HDMI cable and reconnect at the new TV — no reconfiguration needed.

# 12. TV Client: Plain HTML/JS vs React

Plain HTML/JS was selected. The rationale:

# 13. Suggested Build Order

- Step 1: Project scaffold: FastAPI app, SQLite schema, SQLModel models, .env loading.
- Step 2: YouTube API integration: channel lookup, video sync job with APScheduler.
- Step 3: Core API routes: /api/channels, /api/videos, /api/search, /api/session.
- Step 4: TV Client: Home screen → Search screen → Player screen → Watch-Next screen → Lock screen.
- Step 5: Screen time enforcement: session tracking, 5-minute warning, daily reset.
- Step 6: Admin Panel: NiceGUI pages for channel management, settings, watch history.
- Step 7: Pi setup: systemd service, Chromium kiosk mode on boot, .env secrets configuration.

| Product | What It Does | Gap |
| --- | --- | --- |
| YouTube Kids | Curated kids content, limited channel blocking | Cannot whitelist specific channels; algorithm still drives recommendations |
| Google Family Link | Locks device to YouTube Kids | Same limitations as YouTube Kids |
| Circle / Bark | Network-level blocking | All-or-nothing — cannot curate at channel level |
| Pi-hole / OpenDNS | DNS-based domain filtering | Domain-level only; no channel-level control |
| Invidious | Open-source YouTube front-end (self-hosted) | Closest architecturally, but no built-in parental whitelist feature |
| Plex / Jellyfin | Self-hosted media server | Requires pre-downloading content; not a live streaming UI |
| Kidoodle.TV / Amazon Kids+ | Curated alternative platforms | Not YouTube; limited and non-configurable channel selection |


| Operation | Unit Cost | Estimated Daily Usage |
| --- | --- | --- |
| Sync new videos per channel (up to 50 per call) | 1 unit | ~20 channels × 24 syncs = ~480 units |
| Search (runs against local SQLite cache) | 0 units | — |
| Fetch video details | 1 unit per 50 videos | Negligible |
| Total estimated | — | 500–800 units/day  (well under 10,000 limit) |


| Layer | Technology |
| --- | --- |
| Backend framework | Python 3.11+, FastAPI |
| Background jobs | APScheduler (runs within FastAPI process) |
| Database | SQLite via SQLModel (Pydantic + SQLAlchemy) |
| TV Client | Plain HTML5 + CSS3 + Vanilla JavaScript |
| YouTube playback | YouTube IFrame Player API (official, ToS-compliant) |
| Admin Panel | NiceGUI (Python, served within FastAPI) |
| ASGI server | Uvicorn |
| YouTube integration | google-api-python-client (official library) |
| Secrets management | .env file loaded via python-dotenv |
| Runtime on Pi | systemd service, Chromium in kiosk mode on boot |
| Hardware | Raspberry Pi 5, HDMI to TV, power via USB-C |


| Factor | Plain HTML/JS | React |
| --- | --- | --- |
| Build toolchain | None required | Node.js, npm, Vite/webpack build step |
| Deployment on Pi | Copy files; done | Must build before deploy; node_modules on Pi |
| Number of screens | 5 screens — no complexity justifies a framework | 5 screens — overkill |
| State complexity | Low (current video, session, search query) | No complex shared state that justifies React |
| YouTube IFrame API | Trivial (one script tag, global YT object) | Requires wrapper package |
| Long-term maintenance | No dependency rot | Dependencies go stale; breaking major versions |
| Debugging on Pi | Edit file, refresh Chromium | Edit → rebuild → refresh cycle |
