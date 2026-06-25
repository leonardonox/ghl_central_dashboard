from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.metrics_service import MetricsService

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


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
