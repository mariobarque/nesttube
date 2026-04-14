from datetime import datetime, date
from typing import Optional
from sqlmodel import Field, SQLModel


class Channel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    youtube_channel_id: str = Field(unique=True, index=True)
    display_name: str
    category: Optional[str] = Field(default=None)
    thumbnail_url: Optional[str] = Field(default=None)
    added_at: datetime = Field(default_factory=datetime.utcnow)


class Video(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    youtube_video_id: str = Field(unique=True, index=True)
    channel_id: int = Field(foreign_key="channel.id")
    title: str
    thumbnail_url: Optional[str] = Field(default=None)
    duration_seconds: Optional[int] = Field(default=None)
    published_at: Optional[datetime] = Field(default=None)
    synced_at: datetime = Field(default_factory=datetime.utcnow)
    is_live: bool = Field(default=False)


class WatchSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(default=None)
    total_seconds: int = Field(default=0)
    session_date: date = Field(default_factory=date.today)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
