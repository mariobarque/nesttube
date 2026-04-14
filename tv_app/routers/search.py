from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from pydantic import BaseModel

from shared.database import get_session
from shared.models import Video, Channel, Setting

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    youtube_video_id: str
    channel_id: int
    channel_name: str
    title: str
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    published_at: Optional[datetime]


@router.get("", response_model=list[SearchResult])
def search_videos(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(40, le=100),
    session: Session = Depends(get_session),
):
    # Sanitise query to prevent SQLite injection via LIKE
    safe_q = q.replace("%", r"\%").replace("_", r"\_")

    stmt = (
        select(Video)
        .where(Video.title.ilike(f"%{safe_q}%"))
    )

    # Apply video filters from settings
    exclude_live = (session.get(Setting, "exclude_live_videos") or Setting(key="", value="true")).value == "true"
    min_duration = int((session.get(Setting, "min_video_duration_seconds") or Setting(key="", value="0")).value)
    if exclude_live:
        stmt = stmt.where(Video.is_live == False)
    if min_duration > 0:
        stmt = stmt.where(Video.duration_seconds >= min_duration)

    stmt = stmt.order_by(Video.published_at.desc()).limit(limit)

    videos = session.exec(stmt).all()

    cids = list({v.channel_id for v in videos})
    channels_map = {
        c.id: c
        for c in session.exec(select(Channel).where(Channel.id.in_(cids))).all()
    }

    return [
        SearchResult(
            youtube_video_id=v.youtube_video_id,
            channel_id=v.channel_id,
            channel_name=channels_map[v.channel_id].display_name,
            title=v.title,
            thumbnail_url=v.thumbnail_url,
            duration_seconds=v.duration_seconds,
            published_at=v.published_at,
        )
        for v in videos
        if v.channel_id in channels_map
    ]
