from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from shared.database import get_session
from shared.models import Channel

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelRead(BaseModel):
    id: int
    youtube_channel_id: str
    display_name: str
    category: Optional[str]
    thumbnail_url: Optional[str]


class ChannelCreate(BaseModel):
    youtube_channel_id: str
    display_name: str
    category: Optional[str] = None
    thumbnail_url: Optional[str] = None


@router.get("", response_model=list[ChannelRead])
def list_channels(session: Session = Depends(get_session)):
    return session.exec(select(Channel).order_by(Channel.display_name)).all()


@router.get("/categories", response_model=list[str])
def list_categories(session: Session = Depends(get_session)):
    channels = session.exec(select(Channel)).all()
    cats = sorted({c.category for c in channels if c.category})
    return cats


@router.post("", response_model=ChannelRead, status_code=201)
def create_channel(data: ChannelCreate, session: Session = Depends(get_session)):
    if session.exec(
        select(Channel).where(Channel.youtube_channel_id == data.youtube_channel_id)
    ).first():
        raise HTTPException(status_code=409, detail="Channel already exists.")
    channel = Channel(**data.model_dump())
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: int, session: Session = Depends(get_session)):
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found.")
    session.delete(channel)
    session.commit()
