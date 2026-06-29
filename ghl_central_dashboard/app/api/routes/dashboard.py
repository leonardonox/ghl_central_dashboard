from datetime import date, timedelta
from decimal import Decimal
import json
import unicodedata
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ghl_account import GHLAccount
from app.models.opportunity import Opportunity
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


def _decimal_to_float(value: Decimal | None) -> float:
    return float(value or 0)


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


@router.get('/editorial-support')
def editorial_support(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Opportunity, GHLAccount)
        .join(GHLAccount, Opportunity.account_id == GHLAccount.id)
        .where(GHLAccount.active.is_(True))
        .order_by(GHLAccount.name, Opportunity.synced_at.desc())
    ).all()

    groups: dict[int, dict] = {}
    total = 0
    for opportunity, account in rows:
        raw = _raw_dict(opportunity.raw_data)
        if not _support_stage_match(raw):
            continue

        group = groups.setdefault(account.id, {
            'account_id': account.id,
            'account': account.name,
            'count': 0,
            'total_value': 0,
            'items': [],
        })
        value = _decimal_to_float(opportunity.monetary_value)
        group['count'] += 1
        group['total_value'] += value
        group['items'].append({
            'id': opportunity.ghl_opportunity_id,
            'name': _contact_name(raw),
            'email': _contact_field(raw, 'email'),
            'phone': _contact_field(raw, 'phone'),
            'value': value,
            'status': opportunity.status,
            'stage': raw.get('_pipelineStageName') or raw.get('pipelineStageName') or raw.get('stageName'),
            'updated_at': raw.get('lastStageChangeAt') or raw.get('updatedAt') or opportunity.synced_at.isoformat(),
        })
        total += 1

    return {
        'stage': 'Suporte editorial',
        'total': total,
        'groups': sorted(groups.values(), key=lambda item: item['account'].lower()),
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
