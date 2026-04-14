from sqlmodel import SQLModel, create_engine, Session, select, text
from shared.config import DATABASE_URL

# Import all table models so SQLModel metadata is populated before create_all
from shared import models  # noqa: F401

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Add columns that create_all cannot add to existing tables."""
    with Session(engine) as session:
        # Check if is_live column exists on video table
        cols = [
            row[1]
            for row in session.exec(text("PRAGMA table_info('video')")).all()
        ]
        if "is_live" not in cols:
            session.exec(text("ALTER TABLE video ADD COLUMN is_live BOOLEAN DEFAULT 0 NOT NULL"))
            session.commit()


def get_session():
    with Session(engine) as session:
        yield session


def init_default_settings() -> None:
    defaults = {
        "screen_time_limit_minutes": "120",
        "schedule_start": "00:00",
        "schedule_end": "23:59",
        "sync_interval_minutes": "60",
        "exclude_live_videos": "true",
        "min_video_duration_seconds": "240",
    }
    with Session(engine) as session:
        for key, value in defaults.items():
            if not session.get(models.Setting, key):
                session.add(models.Setting(key=key, value=value))
        session.commit()
