from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from pydantic import BaseModel

from shared.database import get_session
from shared.models import Video, Channel, Setting

router = APIRouter(prefix="/videos", tags=["videos"])


class VideoRead(BaseModel):
    id: int
    youtube_video_id: str
    channel_id: int
    channel_name: str
    channel_youtube_id: str
    title: str
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    published_at: Optional[datetime]


@router.get("", response_model=list[VideoRead])
def list_videos(
    channel_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    session: Session = Depends(get_session),
):
    stmt = select(Video)
    if channel_id:
        stmt = stmt.where(Video.channel_id == channel_id)
    if category:
        channel_ids = [
            c.id
            for c in session.exec(
                select(Channel).where(Channel.category == category)
            ).all()
        ]
        stmt = stmt.where(Video.channel_id.in_(channel_ids))

    # Apply video filters from settings
    exclude_live = (session.get(Setting, "exclude_live_videos") or Setting(key="", value="true")).value == "true"
    min_duration = int((session.get(Setting, "min_video_duration_seconds") or Setting(key="", value="0")).value)
    if exclude_live:
        stmt = stmt.where(Video.is_live == False)
    if min_duration > 0:
        stmt = stmt.where(Video.duration_seconds >= min_duration)

    stmt = stmt.order_by(Video.published_at.desc()).offset(offset).limit(limit)
    videos = session.exec(stmt).all()

    cids = list({v.channel_id for v in videos})
    channels_map = {
        c.id: c
        for c in session.exec(select(Channel).where(Channel.id.in_(cids))).all()
    }

    return [
        VideoRead(
            id=v.id,
            youtube_video_id=v.youtube_video_id,
            channel_id=v.channel_id,
            channel_name=channels_map[v.channel_id].display_name,
            channel_youtube_id=channels_map[v.channel_id].youtube_channel_id,
            title=v.title,
            thumbnail_url=v.thumbnail_url,
            duration_seconds=v.duration_seconds,
            published_at=v.published_at,
        )
        for v in videos
        if v.channel_id in channels_map
    ]
