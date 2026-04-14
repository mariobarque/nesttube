# shared/

Backend core shared by both the TV App and the Admin Panel. Nothing in this package renders UI — it only provides data access, configuration, and services.

## Contents

### `config.py`
Loads environment variables from the project-root `.env` file at startup. Exposes:

| Variable | Description |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud API key with YouTube Data API v3 enabled |
| `ADMIN_PASSCODE_HASH` | bcrypt hash of the parent passcode |
| `SECRET_KEY` | Random string for NiceGUI session cookie signing |
| `PORT` | Uvicorn listen port (default `8000`) |
| `BASE_DIR` | Absolute path to the project root |
| `DATA_DIR` | `BASE_DIR/data/` — where `nesttube.db` lives |
| `DATABASE_URL` | SQLite connection URL |

### `models.py`
SQLModel table definitions:

| Model | Purpose |
|---|---|
| `Channel` | An approved YouTube channel (channel ID, name, category, thumbnail) |
| `Video` | A cached video from an approved channel (metadata only — no video bytes stored) |
| `WatchSession` | Daily screen-time record (total seconds watched per day) |
| `Setting` | Key/value store for runtime configuration (screen time limit, schedule, sync interval) |

### `database.py`
Creates the SQLite engine, provides the FastAPI `get_session` dependency, and runs `init_default_settings()` on first boot to seed the `Setting` table with sensible defaults.

### `services/auth.py`
Passcode hashing and verification using `bcrypt` via `passlib`. The plain-text passcode is never stored anywhere — only the hash in `.env`.

### `services/youtube.py`
Wrapper around the official `google-api-python-client` YouTube Data API v3:

- `resolve_channel(url_or_id)` — accepts a YouTube URL, `@handle`, or `UC...` channel ID and returns channel metadata.
- `fetch_channel_videos(channel_id)` — returns up to 50 recent videos from a channel's uploads playlist, including duration (parsed from ISO 8601).

### `services/sync.py`
APScheduler-based background job that periodically calls `fetch_channel_videos` for every approved channel and inserts new videos into the local SQLite catalog. The TV client searches this local catalog, so no YouTube API quota is consumed during searches.

## Data Flow

```
YouTube Data API v3
        │
        ▼  (metadata only, runs on schedule)
services/sync.py
        │
        ▼
SQLite (shared/models.py via shared/database.py)
        │
        ├──> tv_app/routers/  (read — serve catalog to TV)
        └──> admin_panel/     (read/write — manage channels and settings)
```
