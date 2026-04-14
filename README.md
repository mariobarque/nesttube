# NestTube

A self-hosted, parental-controlled YouTube streaming system that runs entirely on a Raspberry Pi 5. It presents children with a curated, fullscreen TV interface where every search result and recommendation comes only from a parent-approved list of YouTube channels.

## Why NestTube?

YouTube's algorithm is designed to maximise engagement, not safety. NestTube replaces the YouTube interface entirely with a controlled experience:

- **Whitelist-only content** — only videos from channels you approve can appear.
- **No algorithmic recommendations** — the "Watch Next" screen is built from your local catalog.
- **Screen time enforcement** — configurable daily limit (default 2 hours) with lock screen and parent unlock.
- **Viewing schedule** — restrict access to certain hours of the day.
- **TV-first design** — runs on a Raspberry Pi 5 connected via HDMI; no phone or tablet needed.

## Project Structure

```
nesttube/
├── main.py              ← FastAPI entry point; wires all components together
├── requirements.txt     ← Python dependencies
├── .env.example         ← Template for secrets and config
│
├── shared/              ← Backend core (database, models, config, services)
│   └── README.md
│
├── tv_app/              ← TV kiosk client (HTML/JS) + API routers
│   └── README.md
│
├── admin_panel/         ← Parent admin panel (NiceGUI)
│   └── README.md
│
└── setup/               ← Raspberry Pi deployment scripts
```

## Quick Start (Development)

```bash
# 1. Copy and fill in the env file
cp .env.example .env
# Edit .env: set YOUTUBE_API_KEY and SECRET_KEY

# 2. Install dependencies
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt     # Linux/macOS

# 3. Run
.venv/Scripts/uvicorn main:app --reload --port 8000
```

- TV client: http://localhost:8000
- Admin panel: http://localhost:8000/admin *(first visit creates your passcode)*

## Raspberry Pi Deployment

See [setup/pi_setup.sh](setup/pi_setup.sh) for step-by-step instructions.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite via SQLModel |
| Background jobs | APScheduler |
| TV Client | Plain HTML5 + CSS3 + Vanilla JS |
| YouTube playback | YouTube IFrame Player API (official) |
| Admin Panel | NiceGUI |
| YouTube data | YouTube Data API v3 (free tier) |
| Secrets | python-dotenv (.env file on the Pi) |
