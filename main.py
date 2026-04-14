from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from shared.database import create_db_and_tables, init_default_settings
from tv_app.routers import channels, videos, search, session
from shared.services.sync import start_scheduler

# Import admin panel — this registers all @ui.page routes with NiceGUI
import admin_panel.panel as admin_panel


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    init_default_settings()
    start_scheduler()
    yield


app = FastAPI(title="NestTube", lifespan=lifespan)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(channels.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(session.router, prefix="/api")

# ── TV Client static files ────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "tv_app" / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def tv_client():
    return FileResponse(STATIC_DIR / "index.html")


# ── Mount NiceGUI (must be last — adds middleware to the FastAPI app) ─────────
admin_panel.mount(app)
