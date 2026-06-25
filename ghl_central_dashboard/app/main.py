import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import accounts, auth, dashboard, sync
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.services.sync_service import GHLSyncService

configure_logging()
settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version='0.1.0')

static_dir = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=static_dir), name='static')

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(dashboard.router)
app.include_router(sync.router)


async def _auto_sync_loop() -> None:
    interval_seconds = max(settings.sync_interval_minutes, 5) * 60
    while True:
        await asyncio.sleep(interval_seconds)
        db = SessionLocal()
        try:
            await GHLSyncService(db).sync_all(days_back=30)
        except Exception:
            logger.exception('Falha na sincronizacao automatica')
        finally:
            db.close()


@app.on_event('startup')
async def start_auto_sync() -> None:
    app.state.auto_sync_task = asyncio.create_task(_auto_sync_loop())


@app.on_event('shutdown')
async def stop_auto_sync() -> None:
    task = getattr(app.state, 'auto_sync_task', None)
    if task:
        task.cancel()


@app.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/')
def dashboard_app():
    return FileResponse(static_dir / 'index.html')
