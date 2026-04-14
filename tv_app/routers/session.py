from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from shared.database import get_session
from shared.models import WatchSession, Setting
from shared.services.auth import verify_passcode

router = APIRouter(prefix="/session", tags=["session"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(session: Session, key: str, default: str) -> str:
    s = session.get(Setting, key)
    return s.value if s else default


def _today_limit_seconds(session: Session, today: date) -> int:
    base = int(_get(session, "screen_time_limit_minutes", "120")) * 60
    ext = session.get(Setting, f"screen_time_extension_{today.isoformat()}")
    return base + (int(ext.value) * 60 if ext else 0)


def _today_seconds(session: Session, today: date) -> int:
    ws = session.exec(
        select(WatchSession).where(WatchSession.session_date == today)
    ).first()
    return ws.total_seconds if ws else 0


# ── schemas ───────────────────────────────────────────────────────────────────

class SessionStatus(BaseModel):
    total_seconds: int
    limit_seconds: int
    remaining_seconds: int
    is_locked: bool
    lock_reason: Optional[str]  # "time_limit" | "schedule" | None


class PingRequest(BaseModel):
    elapsed_seconds: int


class UnlockRequest(BaseModel):
    passcode: str


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/today", response_model=SessionStatus)
def get_today_status(session: Session = Depends(get_session)):
    today = date.today()
    total = _today_seconds(session, today)
    limit = _today_limit_seconds(session, today)

    # Schedule check
    now = datetime.now().time()
    start_str = _get(session, "schedule_start", "00:00")
    end_str = _get(session, "schedule_end", "23:59")
    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))
    from datetime import time as dtime
    if not (dtime(sh, sm) <= now <= dtime(eh, em)):
        return SessionStatus(
            total_seconds=total,
            limit_seconds=limit,
            remaining_seconds=max(0, limit - total),
            is_locked=True,
            lock_reason="schedule",
        )

    remaining = max(0, limit - total)
    return SessionStatus(
        total_seconds=total,
        limit_seconds=limit,
        remaining_seconds=remaining,
        is_locked=remaining == 0,
        lock_reason="time_limit" if remaining == 0 else None,
    )


@router.post("/ping")
def ping_session(req: PingRequest, session: Session = Depends(get_session)):
    today = date.today()
    # Cap at 120 s per ping to prevent client-side manipulation
    elapsed = max(0, min(req.elapsed_seconds, 120))

    ws = session.exec(
        select(WatchSession).where(WatchSession.session_date == today)
    ).first()
    if ws:
        ws.total_seconds += elapsed
        session.add(ws)
    else:
        session.add(WatchSession(total_seconds=elapsed, session_date=today))
    session.commit()
    return {"ok": True}


@router.post("/unlock")
def unlock_session(req: UnlockRequest, session: Session = Depends(get_session)):
    if not verify_passcode(req.passcode):
        raise HTTPException(status_code=401, detail="Invalid passcode.")

    today = date.today()
    ext_key = f"screen_time_extension_{today.isoformat()}"
    ext = session.get(Setting, ext_key)
    if ext:
        ext.value = str(int(ext.value) + 30)
        session.add(ext)
    else:
        session.add(Setting(key=ext_key, value="30"))
    session.commit()
    return {"ok": True, "added_minutes": 30}
