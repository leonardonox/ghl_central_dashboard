import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.services.sync_service import GHLSyncService

router = APIRouter(prefix='/sync', tags=['sync'])

sync_state = {
    'running': False,
    'started_at': None,
    'finished_at': None,
    'days_back': None,
    'result': None,
    'error': None,
}


async def _run_background_sync(days_back: int) -> None:
    sync_state.update({
        'running': True,
        'started_at': datetime.utcnow().isoformat(),
        'finished_at': None,
        'days_back': days_back,
        'result': None,
        'error': None,
    })
    db = SessionLocal()
    try:
        sync_state['result'] = await GHLSyncService(db).sync_all(days_back=days_back)
    except Exception as exc:
        sync_state['error'] = str(exc)
    finally:
        db.close()
        sync_state['running'] = False
        sync_state['finished_at'] = datetime.utcnow().isoformat()


@router.post('/run')
async def run_sync(days_back: int = 7, db: Session = Depends(get_db)):
    return await GHLSyncService(db).sync_all(days_back=days_back)


@router.post('/start')
async def start_sync(days_back: int = 7):
    if sync_state['running']:
        return {'status': 'running', **sync_state}
    asyncio.create_task(_run_background_sync(days_back))
    return {'status': 'started', 'days_back': days_back}


@router.get('/status')
def sync_status():
    return sync_state
