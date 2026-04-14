"""
NiceGUI admin panel — all pages are registered here.
Import this module before calling ui.run_with(app).
"""
from datetime import date
from fastapi import FastAPI
from nicegui import ui, app as ng_app
from sqlmodel import Session, select

from shared import config
from shared.database import engine
from shared.models import Channel, Video, WatchSession, Setting
from shared.services.auth import verify_passcode, hash_passcode
from shared.services.youtube import resolve_channel
from shared.services.sync import sync_channel, sync_all_channels


# ── auth helpers ──────────────────────────────────────────────────────────────

def _is_auth() -> bool:
    return ng_app.storage.user.get("admin_authenticated", False)


def _require_auth() -> bool:
    """Redirect to login if not authenticated. Returns True if authenticated."""
    if not _is_auth():
        ui.navigate.to("/")
        return False
    return True


# ── db helpers ────────────────────────────────────────────────────────────────

def _get_setting(session: Session, key: str, default: str) -> str:
    s = session.get(Setting, key)
    return s.value if s else default


def _set_setting(session: Session, key: str, value: str) -> None:
    s = session.get(Setting, key)
    if s:
        s.value = value
        session.add(s)
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


# ── shared nav ────────────────────────────────────────────────────────────────

def _nav_header() -> None:
    with ui.header().classes("bg-slate-800 text-white items-center"):
        ui.label("NestTube Admin").classes("font-bold text-lg mr-6")
        ui.button("Channels", on_click=lambda: ui.navigate.to("/channels")).props(
            "flat dense color=white"
        )
        ui.button("Settings", on_click=lambda: ui.navigate.to("/settings")).props(
            "flat dense color=white"
        )
        ui.button("History", on_click=lambda: ui.navigate.to("/history")).props(
            "flat dense color=white"
        )
        ui.space()

        def _logout():
            ng_app.storage.user["admin_authenticated"] = False
            ui.navigate.to("/")

        ui.button("Logout", on_click=_logout).props("flat dense color=white outline")


# ── login page ────────────────────────────────────────────────────────────────

@ui.page("/")
def login_page() -> None:
    if _is_auth():
        ui.navigate.to("/channels")
        return

    with ui.card().classes("absolute-center").style("min-width:360px;padding:2rem"):
        ui.label("NestTube Admin").classes("text-2xl font-bold text-center w-full")
        ui.separator()

        # ── first-time setup ──────────────────────────────────────────────────
        if not config.ADMIN_PASSCODE_HASH:
            ui.label("First-time setup — create your admin passcode").classes(
                "text-amber-600 text-sm"
            )
            new_pw = ui.input(
                "New passcode", password=True, password_toggle_button=True
            ).classes("w-full")
            confirm_pw = ui.input(
                "Confirm passcode", password=True, password_toggle_button=True
            ).classes("w-full")

            def _setup():
                if len(new_pw.value) < 4:
                    ui.notify("Passcode must be at least 4 characters.", type="negative")
                    return
                if new_pw.value != confirm_pw.value:
                    ui.notify("Passcodes do not match.", type="negative")
                    return
                h = hash_passcode(new_pw.value)
                # Persist to .env
                env_path = config.BASE_DIR / ".env"
                lines: list[str] = []
                written = False
                if env_path.exists():
                    for line in env_path.read_text().splitlines(keepends=True):
                        if line.startswith("ADMIN_PASSCODE_HASH="):
                            lines.append(f"ADMIN_PASSCODE_HASH={h}\n")
                            written = True
                        else:
                            lines.append(line)
                if not written:
                    lines.append(f"ADMIN_PASSCODE_HASH={h}\n")
                env_path.write_text("".join(lines))
                config.ADMIN_PASSCODE_HASH = h
                ng_app.storage.user["admin_authenticated"] = True
                ui.notify("Passcode created. Welcome!", type="positive")
                ui.navigate.to("/channels")

            ui.button("Create passcode", on_click=_setup).classes("w-full mt-2")

        # ── normal login ──────────────────────────────────────────────────────
        else:
            pw = ui.input(
                "Passcode", password=True, password_toggle_button=True
            ).classes("w-full")

            def _login():
                if verify_passcode(pw.value):
                    ng_app.storage.user["admin_authenticated"] = True
                    ui.navigate.to("/channels")
                else:
                    ui.notify("Invalid passcode.", type="negative")
                    pw.value = ""

            pw.on("keydown.enter", lambda _: _login())
            ui.button("Login", on_click=_login).classes("w-full mt-2")


# ── channels page ─────────────────────────────────────────────────────────────

@ui.page("/channels")
def channels_page() -> None:
    if not _require_auth():
        return
    _nav_header()
    ui.label("Channel Management").classes("text-2xl font-bold m-4")

    channel_list = ui.column().classes("w-full px-4 gap-2")

    def _refresh():
        channel_list.clear()
        with channel_list, Session(engine) as s:
            channels = s.exec(select(Channel).order_by(Channel.display_name)).all()
        if not channels:
            with channel_list:
                ui.label("No channels yet. Add one below.").classes("text-gray-400")
            return
        for ch in channels:
            with channel_list:
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("items-center gap-3"):
                            if ch.thumbnail_url:
                                ui.image(ch.thumbnail_url).style(
                                    "width:40px;height:40px;border-radius:50%;object-fit:cover"
                                )
                            with ui.column().classes("gap-0"):
                                ui.label(ch.display_name).classes("font-bold")
                                ui.label(
                                    f"{ch.category or 'No category'}  ·  {ch.youtube_channel_id}"
                                ).classes("text-xs text-gray-500")

                        with ui.row().classes("gap-1"):

                            def _make_sync(channel: Channel):
                                def _do():
                                    with Session(engine) as s:
                                        c = s.get(Channel, channel.id)
                                        sync_channel(s, c)
                                    ui.notify(f"Synced '{channel.display_name}'", type="positive")

                                return _do

                            def _make_delete(ch_id: int, ch_name: str):
                                def _do():
                                    with Session(engine) as s:
                                        c = s.get(Channel, ch_id)
                                        if c:
                                            for v in s.exec(
                                                select(Video).where(Video.channel_id == ch_id)
                                            ).all():
                                                s.delete(v)
                                            s.delete(c)
                                            s.commit()
                                    ui.notify(f"Deleted '{ch_name}'", type="warning")
                                    _refresh()

                                return _do

                            ui.button(
                                "Sync", on_click=_make_sync(ch), icon="sync"
                            ).props("flat dense")
                            ui.button(
                                "Delete",
                                on_click=_make_delete(ch.id, ch.display_name),
                                icon="delete",
                            ).props("flat dense color=negative")

    with ui.card().classes("mx-4 mb-4"):
        ui.label("Add Channel").classes("text-lg font-semibold")
        with ui.row().classes("w-full gap-2 items-end flex-wrap"):
            url_input = ui.input("YouTube URL, @handle, or channel ID").style(
                "min-width:300px"
            )
            cat_input = ui.input("Category (optional)")

            async def _add():
                url = url_input.value.strip()
                if not url:
                    ui.notify("Enter a channel URL or handle.", type="warning")
                    return
                spinner = ui.spinner(size="sm")
                info = resolve_channel(url)
                spinner.delete()
                if not info:
                    ui.notify(
                        "Channel not found. Check the URL or handle.", type="negative"
                    )
                    return
                with Session(engine) as s:
                    if s.exec(
                        select(Channel).where(
                            Channel.youtube_channel_id == info["youtube_channel_id"]
                        )
                    ).first():
                        ui.notify("Channel already added.", type="warning")
                        return
                    ch = Channel(
                        youtube_channel_id=info["youtube_channel_id"],
                        display_name=info["display_name"],
                        thumbnail_url=info.get("thumbnail_url"),
                        category=cat_input.value.strip() or None,
                    )
                    s.add(ch)
                    s.commit()
                    s.refresh(ch)
                    sync_channel(s, ch)
                ui.notify(f"Added '{info['display_name']}'", type="positive")
                url_input.value = ""
                cat_input.value = ""
                _refresh()

            ui.button("Add Channel", on_click=_add, icon="add")

    ui.separator().classes("mx-4")
    _refresh()


# ── settings page ─────────────────────────────────────────────────────────────

@ui.page("/settings")
def settings_page() -> None:
    if not _require_auth():
        return
    _nav_header()
    ui.label("Settings").classes("text-2xl font-bold m-4")

    with Session(engine) as s:
        cur_limit = _get_setting(s, "screen_time_limit_minutes", "120")
        cur_start = _get_setting(s, "schedule_start", "00:00")
        cur_end = _get_setting(s, "schedule_end", "23:59")
        cur_sync = _get_setting(s, "sync_interval_minutes", "60")
        cur_exclude_live = _get_setting(s, "exclude_live_videos", "true")
        cur_min_duration = _get_setting(s, "min_video_duration_seconds", "240")

    with ui.column().classes("px-4 gap-4 w-full max-w-lg"):
        with ui.card().classes("w-full"):
            ui.label("Screen Time").classes("text-lg font-semibold")
            limit_inp = ui.number(
                "Daily limit (minutes)", value=int(cur_limit), min=10, max=480, step=10
            ).classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Viewing Schedule").classes("text-lg font-semibold")
            ui.label("Set 00:00 – 23:59 to allow all day.").classes("text-xs text-gray-500")
            start_inp = ui.input("Start time (HH:MM)", value=cur_start).classes("w-full")
            end_inp = ui.input("End time (HH:MM)", value=cur_end).classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Sync Interval").classes("text-lg font-semibold")
            sync_inp = ui.number(
                "Minutes between syncs", value=int(cur_sync), min=15, max=1440, step=15
            ).classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Video Filters").classes("text-lg font-semibold")
            ui.label("Applied during sync — existing videos are not removed.").classes(
                "text-xs text-gray-500"
            )
            exclude_live_inp = ui.checkbox(
                "Exclude live and upcoming videos", value=cur_exclude_live == "true"
            )
            min_dur_inp = ui.number(
                "Minimum video duration (seconds)", value=int(cur_min_duration),
                min=0, max=3600, step=10
            ).classes("w-full")

        def _save():
            with Session(engine) as s:
                _set_setting(s, "screen_time_limit_minutes", str(int(limit_inp.value)))
                _set_setting(s, "schedule_start", start_inp.value.strip())
                _set_setting(s, "schedule_end", end_inp.value.strip())
                _set_setting(s, "sync_interval_minutes", str(int(sync_inp.value)))
                _set_setting(s, "exclude_live_videos", "true" if exclude_live_inp.value else "false")
                _set_setting(s, "min_video_duration_seconds", str(int(min_dur_inp.value)))
            ui.notify("Settings saved.", type="positive")

        ui.button("Save Settings", on_click=_save, icon="save").classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Manual Sync").classes("text-lg font-semibold")

            def _sync_now():
                sync_all_channels()
                ui.notify("Sync complete.", type="positive")

            ui.button("Sync All Channels Now", on_click=_sync_now, icon="sync").classes(
                "w-full"
            )

        with ui.card().classes("w-full"):
            ui.label("Force Unlock Screen Time Today").classes("text-lg font-semibold")
            ui.label("Resets today's watch-time counter to zero.").classes(
                "text-xs text-gray-500"
            )

            def _reset():
                today = date.today()
                with Session(engine) as s:
                    ws = s.exec(
                        select(WatchSession).where(WatchSession.session_date == today)
                    ).first()
                    if ws:
                        ws.total_seconds = 0
                        s.add(ws)
                        s.commit()
                    ext = s.get(Setting, f"screen_time_extension_{today.isoformat()}")
                    if ext:
                        s.delete(ext)
                        s.commit()
                ui.notify("Screen time reset for today.", type="positive")

            ui.button(
                "Reset Today's Screen Time", on_click=_reset, icon="lock_open"
            ).props("color=warning").classes("w-full")


# ── history page ──────────────────────────────────────────────────────────────

@ui.page("/history")
def history_page() -> None:
    if not _require_auth():
        return
    _nav_header()
    ui.label("Watch History — Last 30 Days").classes("text-2xl font-bold m-4")

    with Session(engine) as s:
        sessions = s.exec(
            select(WatchSession).order_by(WatchSession.session_date.desc()).limit(30)
        ).all()
        limit_minutes = int(_get_setting(s, "screen_time_limit_minutes", "120"))

    rows = [
        {
            "date": str(ws.session_date),
            "watched": f"{ws.total_seconds // 60}m {ws.total_seconds % 60}s",
            "limit": f"{limit_minutes}m",
            "pct": min(100, round(ws.total_seconds / (limit_minutes * 60) * 100)),
        }
        for ws in sessions
    ]

    columns = [
        {"name": "date", "label": "Date", "field": "date", "align": "left"},
        {"name": "watched", "label": "Watched", "field": "watched", "align": "left"},
        {"name": "limit", "label": "Daily Limit", "field": "limit", "align": "left"},
        {"name": "pct", "label": "% Used", "field": "pct", "align": "left"},
    ]

    ui.table(columns=columns, rows=rows).classes("mx-4 w-full max-w-2xl")


# ── wire NiceGUI into FastAPI ─────────────────────────────────────────────────

def mount(fastapi_app: FastAPI) -> None:
    ui.run_with(fastapi_app, storage_secret=config.SECRET_KEY, mount_path="/admin")
