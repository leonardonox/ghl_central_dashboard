from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.sync_service import GHLSyncService

router = APIRouter(prefix='/sync', tags=['sync'])


@router.post('/run')
async def run_sync(days_back: int = 7, db: Session = Depends(get_db)):
    return await GHLSyncService(db).sync_all(days_back=days_back)
