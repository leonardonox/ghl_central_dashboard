import asyncio
from datetime import date, timedelta
import json
import unicodedata
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decrypt_token
from app.integrations.ghl.client import GHLClient
from app.models.ghl_account import GHLAccount
from app.services.metrics_service import MetricsService

router = APIRouter(prefix='/dashboard', tags=['dashboard'])
EDITORIAL_STAGE = 'suporte editorial'


def _clean_text(value: object) -> str:
    normalized = unicodedata.normalize('NFKD', str(value or ''))
    return normalized.encode('ascii', 'ignore').decode().lower()


def _raw_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _walk_values(value: object, parent_key: str = '') -> list[str]:
    if isinstance(value, dict):
        values = []
        for key, child in value.items():
            path = f'{parent_key}.{key}' if parent_key else str(key)
            values.extend(_walk_values(child, path))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(_walk_values(child, parent_key))
        return values
    if isinstance(value, (str, int, float)):
        key = _clean_text(parent_key)
        text = str(value)
        if any(term in key for term in ('stage', 'pipeline', 'status', 'field', 'custom')):
            return [text]
    return []


def _support_stage_match(raw_data: dict | None) -> bool:
    raw = _raw_dict(raw_data)
    direct_values = [
        raw.get('_pipelineStageName'),
        raw.get('pipelineStageName'),
        raw.get('stageName'),
        raw.get('stage'),
        raw.get('pipelineStage'),
    ]
    candidates = [str(value) for value in direct_values if value]
    candidates.extend(_walk_values(raw))
    return any(EDITORIAL_STAGE in _clean_text(value) for value in candidates)


def _contact_name(raw_data: dict | None) -> str:
    raw = _raw_dict(raw_data)
    contact = raw.get('contact') or {}
    return (
        raw.get('name')
        or raw.get('contactName')
        or contact.get('name')
        or contact.get('contactName')
        or 'Sem nome'
    )


def _contact_field(raw_data: dict | None, field: str) -> str | None:
    raw = _raw_dict(raw_data)
    contact = raw.get('contact') or {}
    return raw.get(field) or contact.get(field)


def _money_value(raw_data: dict | None) -> float:
    raw = _raw_dict(raw_data)
    try:
        return float(raw.get('monetaryValue') or raw.get('value') or 0)
    except (TypeError, ValueError):
        return 0


def _stage_infos(payload: dict) -> list[dict[str, str | None]]:
    infos = []
    for pipeline in payload.get('pipelines') or []:
        pipeline_id = pipeline.get('id') or pipeline.get('_id')
        pipeline_name = pipeline.get('name')
        for stage in pipeline.get('stages') or []:
            stage_name = stage.get('name')
            if EDITORIAL_STAGE not in _clean_text(stage_name):
                continue
            stage_id = stage.get('id') or stage.get('_id') or stage.get('stageId')
            if stage_id:
                infos.append({
                    'pipeline_id': pipeline_id,
                    'pipeline_name': pipeline_name,
                    'stage_id': str(stage_id),
                    'stage_name': stage_name,
                })
    return infos


async def _fetch_stage_opportunities(client: GHLClient, location_id: str, stage_info: dict[str, str | None]) -> list[dict]:
    params = {
        'location_id': location_id,
        'pipeline_stage_id': stage_info['stage_id'],
        'limit': 100,
    }
    if stage_info.get('pipeline_id'):
        params['pipeline_id'] = stage_info['pipeline_id']

    opportunities = []
    page_count = 0
    while page_count < 20:
        page_count += 1
        data = await client.get('/opportunities/search', params=params)
        page_opportunities = data.get('opportunities') or []
        if not page_opportunities:
            break

        for item in page_opportunities:
            enriched = {
                **item,
                '_pipelineName': stage_info.get('pipeline_name'),
                '_pipelineStageName': stage_info.get('stage_name'),
            }
            if str(item.get('pipelineStageId') or '') == stage_info['stage_id'] or _support_stage_match(enriched):
                opportunities.append(enriched)

        meta = data.get('meta') or {}
        if not meta.get('startAfter') or not meta.get('startAfterId'):
            break
        params['startAfter'] = meta['startAfter']
        params['startAfterId'] = meta['startAfterId']

    return opportunities


async def _fetch_editorial_account(account: GHLAccount) -> dict:
    group = {
        'account_id': account.id,
        'account': account.name,
        'count': 0,
        'total_value': 0,
        'items': [],
        'error': None,
    }
    try:
        client = GHLClient(decrypt_token(account.api_token_encrypted))
        pipelines = await client.get('/opportunities/pipelines', params={'locationId': account.location_id})
        stages = _stage_infos(pipelines)
        if not stages:
            return group

        stage_results = await asyncio.gather(*[
            _fetch_stage_opportunities(client, account.location_id, stage)
            for stage in stages
        ])
        for opportunities in stage_results:
            for raw in opportunities:
                value = _money_value(raw)
                group['count'] += 1
                group['total_value'] += value
                group['items'].append({
                    'id': raw.get('id'),
                    'name': _contact_name(raw),
                    'email': _contact_field(raw, 'email'),
                    'phone': _contact_field(raw, 'phone'),
                    'value': value,
                    'status': raw.get('status'),
                    'stage': raw.get('_pipelineStageName') or raw.get('pipelineStageName') or raw.get('stageName'),
                    'updated_at': raw.get('lastStageChangeAt') or raw.get('updatedAt') or raw.get('createdAt'),
                })
    except Exception as exc:
        group['error'] = str(exc)
    return group


@router.get('/compare-dates')
def compare_dates(
    date_a: date = Query(...),
    date_b: date = Query(...),
    account_id: int | None = None,
    db: Session = Depends(get_db),
):
    return MetricsService(db).compare_dates(date_a, date_b, account_id)


@router.get('/summary')
def summary(db: Session = Depends(get_db)):
    today = date.today()
    yesterday = today - timedelta(days=1)
    metrics = MetricsService(db)
    return {
        'today': today.isoformat(),
        'leads_today': metrics.total_leads_by_date(today),
        'leads_yesterday': metrics.total_leads_by_date(yesterday),
        'comparison': metrics.compare_dates(yesterday, today),
    }


@router.get('/ranking')
def ranking(
    start_date: date,
    end_date: date,
    account_id: int | None = None,
    db: Session = Depends(get_db),
):
    return MetricsService(db).ranking_by_period(start_date, end_date, account_id)


@router.get('/performance')
def performance(
    start_date: date,
    end_date: date,
    account_id: int | None = None,
    db: Session = Depends(get_db),
):
    return MetricsService(db).performance_by_period(start_date, end_date, account_id)


@router.get('/comparison')
def comparison(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    return MetricsService(db).comparison_by_period(start_date, end_date)


@router.get('/executive')
def executive(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    return MetricsService(db).executive_dashboard(start_date, end_date)


@router.get('/sla')
def sla(
    start_date: date,
    end_date: date,
    sla_hours: int = 2,
    db: Session = Depends(get_db),
):
    return MetricsService(db).sla_dashboard(start_date, end_date, sla_hours)


@router.get('/editorial-support')
async def editorial_support(db: Session = Depends(get_db)):
    accounts = list(db.query(GHLAccount).filter(GHLAccount.active.is_(True)).order_by(GHLAccount.name).all())
    groups = await asyncio.gather(*[_fetch_editorial_account(account) for account in accounts])
    visible_groups = [group for group in groups if group['count'] or group['error']]
    total = sum(group['count'] for group in visible_groups)

    return {
        'stage': 'Suporte editorial',
        'total': total,
        'source': 'ghl-live',
        'groups': sorted(visible_groups, key=lambda item: item['account'].lower()),
    }


@router.post('/snapshots/build')
def build_snapshots(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    return MetricsService(db).build_daily_snapshots(start_date, end_date)


@router.get('/snapshots')
def snapshots(
    start_date: date,
    end_date: date,
    account_id: int | None = None,
    db: Session = Depends(get_db),
):
    return MetricsService(db).list_daily_snapshots(start_date, end_date, account_id)
