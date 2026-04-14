import logging
from datetime import datetime
from sqlmodel import Session, select
from apscheduler.schedulers.background import BackgroundScheduler

from shared.database import engine
from shared.models import Channel, Video, Setting
from shared.services.youtube import fetch_channel_videos

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(daemon=True)


def sync_channel(session: Session, channel: Channel) -> int:
    """Sync one channel. Returns number of new videos added."""
    videos = fetch_channel_videos(channel.youtube_channel_id)
    new_count = 0

    # Read filter settings
    exclude_live = (session.get(Setting, "exclude_live_videos") or Setting(key="", value="true")).value == "true"
    min_duration = int((session.get(Setting, "min_video_duration_seconds") or Setting(key="", value="0")).value)

    for v in videos:
        # Filter: skip live/upcoming videos
        if exclude_live and v.get("live_broadcast_content", "none") in ("live", "upcoming"):
            continue

        # Filter: skip videos shorter than minimum duration
        if min_duration > 0 and (v.get("duration_seconds") or 0) < min_duration:
            continue

        exists = session.exec(
            select(Video).where(Video.youtube_video_id == v["youtube_video_id"])
        ).first()
        if exists:
            continue

        published_at: datetime | None = None
        if v.get("published_at"):
            try:
                published_at = datetime.fromisoformat(
                    v["published_at"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except ValueError:
                pass

        session.add(
            Video(
                youtube_video_id=v["youtube_video_id"],
                channel_id=channel.id,
                title=v["title"],
                thumbnail_url=v["thumbnail_url"],
                duration_seconds=v["duration_seconds"],
                published_at=published_at,
                is_live=v.get("live_broadcast_content", "none") in ("live", "upcoming"),
            )
        )
        new_count += 1

    if new_count:
        session.commit()
        logger.info("Synced %d new video(s) for '%s'", new_count, channel.display_name)
    return new_count


def sync_all_channels() -> None:
    logger.info("Starting full channel sync…")
    with Session(engine) as session:
        channels = session.exec(select(Channel)).all()
        for ch in channels:
            try:
                sync_channel(session, ch)
            except Exception as exc:
                logger.error("Error syncing channel '%s': %s", ch.display_name, exc)
    logger.info("Full channel sync complete.")


def _get_interval() -> int:
    with Session(engine) as session:
        s = session.get(Setting, "sync_interval_minutes")
        return int(s.value) if s else 60


def start_scheduler() -> None:
    interval = _get_interval()
    _scheduler.add_job(
        sync_all_channels,
        "interval",
        minutes=interval,
        id="channel_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — sync every %d minute(s).", interval)
