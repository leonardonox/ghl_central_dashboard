import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import decrypt_token
from app.integrations.ghl.client import GHLClient
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.opportunity import Opportunity
from app.repositories.account_repository import AccountRepository
from app.services.sync_service import GHLSyncService

router = APIRouter(prefix='/sync', tags=['sync'])
MAX_SYNC_DAYS = 90

sync_state = {
    'running': False,
    'started_at': None,
    'finished_at': None,
    'days_back': None,
    'account_ids': None,
    'result': None,
    'error': None,
}


async def _run_background_sync(days_back: int, account_ids: list[int] | None = None) -> None:
    days_back = max(1, min(days_back, MAX_SYNC_DAYS))
    sync_state.update({
        'running': True,
        'started_at': datetime.utcnow().isoformat(),
        'finished_at': None,
        'days_back': days_back,
        'account_ids': account_ids,
        'result': None,
        'error': None,
    })
    db = SessionLocal()
    try:
        sync_state['result'] = await GHLSyncService(db).sync_all(days_back=days_back, account_ids=account_ids)
    except Exception as exc:
        sync_state['error'] = str(exc)
    finally:
        db.close()
        sync_state['running'] = False
        sync_state['finished_at'] = datetime.utcnow().isoformat()


@router.post('/run')
async def run_sync(
    days_back: int = 7,
    account_ids: list[int] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    days_back = max(1, min(days_back, MAX_SYNC_DAYS))
    return await GHLSyncService(db).sync_all(days_back=days_back, account_ids=account_ids)


@router.post('/start')
async def start_sync(days_back: int = 7, account_ids: list[int] | None = Query(default=None)):
    days_back = max(1, min(days_back, MAX_SYNC_DAYS))
    if sync_state['running']:
        return {'status': 'running', **sync_state}
    asyncio.create_task(_run_background_sync(days_back, account_ids))
    return {'status': 'started', 'days_back': days_back, 'account_ids': account_ids}


@router.get('/status')
def sync_status():
    return sync_state


@router.get('/audit')
async def audit_sync(days_back: int = 7, db: Session = Depends(get_db)):
    start_date = datetime.utcnow() - timedelta(days=days_back)
    service = GHLSyncService(db)
    rows = []

    for account in AccountRepository(db).list_active():
        row = {
            'account_id': account.id,
            'account': account.name,
            'local_contacts': int(db.scalar(
                select(func.count(Lead.id)).where(
                    Lead.account_id == account.id,
                    Lead.ghl_created_at >= start_date,
                )
            ) or 0),
            'local_opportunities': int(db.scalar(
                select(func.count(Opportunity.id)).where(
                    Opportunity.account_id == account.id,
                    Opportunity.ghl_created_at >= start_date,
                )
            ) or 0),
            'local_conversations': int(db.scalar(
                select(func.count(Conversation.id)).where(
                    Conversation.account_id == account.id,
                    Conversation.last_message_date >= start_date,
                )
            ) or 0),
            'ghl_contacts': None,
            'ghl_opportunities': None,
            'ghl_conversations': None,
            'status': 'ok',
            'error': None,
        }
        try:
            client = GHLClient(decrypt_token(account.api_token_encrypted))
            contacts = await service._fetch_contacts(client, account.location_id, start_date)
            stages = await service._fetch_pipeline_stages(client, account.location_id)
            opportunities = await service._fetch_opportunities(client, account.location_id, start_date, stages)
            conversations = await service._fetch_conversations(client, account.location_id, start_date)
            row['ghl_contacts'] = len(contacts)
            row['ghl_opportunities'] = len(opportunities)
            row['ghl_conversations'] = len(conversations)
        except Exception as exc:
            row['status'] = 'error'
            row['error'] = str(exc)
        rows.append(row)

    return {
        'days_back': days_back,
        'start_date': start_date.isoformat(),
        'accounts': len(rows),
        'rows': rows,
    }
