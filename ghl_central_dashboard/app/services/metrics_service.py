import unicodedata
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.daily_snapshot import DailySnapshot
from app.models.ghl_account import GHLAccount
from app.models.lead import Lead
from app.models.opportunity import Opportunity


CHANNELS = [
    '1. JA PUBLIQUEI',
    '2. RECEBI UM CONVITE',
    '3. POR MEIO DO GOOGLE',
    '4. POR INDICACAO',
    '5. INSTAGRAM/FACEBOOK',
    '6. LINKEDIN',
]

SALE_STATUSES = {'won', 'closed', 'won_status'}
LOCAL_TIMEZONE = ZoneInfo('America/Sao_Paulo')
WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom']


class MetricsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _period_range(self, start_date: date, end_date: date) -> tuple[datetime, datetime]:
        local_start = datetime.combine(start_date, time.min, tzinfo=LOCAL_TIMEZONE)
        local_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
        start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
        end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
        return start, end

    def _day_range(self, target_date: date) -> tuple[datetime, datetime]:
        return self._period_range(target_date, target_date)

    def _local_date(self, value: datetime) -> date:
        return value.replace(tzinfo=timezone.utc).astimezone(LOCAL_TIMEZONE).date()

    def _previous_period(self, start_date: date, end_date: date) -> tuple[date, date]:
        days = (end_date - start_date).days + 1
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)
        return previous_start, previous_end

    def _percent(self, numerator: int | float, denominator: int | float) -> float:
        if not denominator:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    def _change_percent(self, current: int | float, previous: int | float) -> float:
        if not previous:
            return 0.0 if not current else 100.0
        return round(((current - previous) / previous) * 100, 2)

    def _insert(self, model):
        if self.db.bind and self.db.bind.dialect.name == 'sqlite':
            return sqlite_insert(model)
        return insert(model)

    def _clean_text(self, value: str | None) -> str:
        normalized = unicodedata.normalize('NFKD', value or '')
        return normalized.encode('ascii', 'ignore').decode().lower()

    def _normalize_channel(self, value: str | None) -> str | None:
        clean = self._clean_text(value)
        if 'ja publiquei' in clean:
            return '1. JA PUBLIQUEI'
        if 'recebi um convite' in clean:
            return '2. RECEBI UM CONVITE'
        if 'google' in clean:
            return '3. POR MEIO DO GOOGLE'
        if 'indicacao' in clean:
            return '4. POR INDICACAO'
        if 'instagram' in clean or 'facebook' in clean:
            return '5. INSTAGRAM/FACEBOOK'
        if 'linkedin' in clean:
            return '6. LINKEDIN'
        return None

    def _tags_from_lead(self, lead: Lead) -> list[str]:
        return list((lead.raw_data or {}).get('tags') or [])

    def _tags_from_opportunity(self, opportunity: Opportunity) -> list[str]:
        raw = opportunity.raw_data or {}
        tags = list((raw.get('contact') or {}).get('tags') or [])
        for relation in raw.get('relations') or []:
            for tag in relation.get('tags') or []:
                if tag not in tags:
                    tags.append(tag)
        return tags

    def _lead_channel(self, lead: Lead) -> str | None:
        source_channel = self._normalize_channel(lead.source)
        if source_channel:
            return source_channel
        for tag in self._tags_from_lead(lead):
            tag_channel = self._normalize_channel(tag)
            if tag_channel:
                return tag_channel
        return None

    def _opportunity_channel(self, opportunity: Opportunity) -> str | None:
        source_channel = self._normalize_channel(opportunity.source)
        if source_channel:
            return source_channel
        for tag in self._tags_from_opportunity(opportunity):
            tag_channel = self._normalize_channel(tag)
            if tag_channel:
                return tag_channel
        return None

    def _has_hsm(self, tags: list[str]) -> bool:
        return any('hsm enviado' in self._clean_text(str(tag)) for tag in tags)

    def _has_attendance(self, tags: list[str]) -> bool:
        return any('em atendimento' in self._clean_text(str(tag)) for tag in tags)

    def _has_tag(self, tags: list[str], text: str) -> bool:
        clean_text = self._clean_text(text)
        return any(clean_text in self._clean_text(str(tag)) for tag in tags)

    def _active_account_filter(self, model, account_id: int | None = None):
        stmt = select(model).join(GHLAccount, model.account_id == GHLAccount.id).where(GHLAccount.active.is_(True))
        if account_id:
            stmt = stmt.where(model.account_id == account_id)
        return stmt

    def total_leads_by_date(self, target_date: date, account_id: int | None = None) -> int:
        start, end = self._day_range(target_date)
        stmt = (
            select(func.count(Opportunity.id))
            .join(GHLAccount, Opportunity.account_id == GHLAccount.id)
            .where(
                Opportunity.ghl_created_at >= start,
                Opportunity.ghl_created_at < end,
                GHLAccount.active.is_(True),
            )
        )
        if account_id:
            stmt = stmt.where(Opportunity.account_id == account_id)
        return int(self.db.scalar(stmt) or 0)

    def total_sales_by_date(self, target_date: date, account_id: int | None = None) -> int:
        start, end = self._day_range(target_date)
        stmt = (
            select(func.count(Opportunity.id))
            .join(GHLAccount, Opportunity.account_id == GHLAccount.id)
            .where(
                Opportunity.ghl_created_at >= start,
                Opportunity.ghl_created_at < end,
                Opportunity.status.in_(SALE_STATUSES),
                GHLAccount.active.is_(True),
            )
        )
        if account_id:
            stmt = stmt.where(Opportunity.account_id == account_id)
        return int(self.db.scalar(stmt) or 0)

    def compare_dates(self, date_a: date, date_b: date, account_id: int | None = None) -> dict:
        leads_a = self.total_leads_by_date(date_a, account_id)
        leads_b = self.total_leads_by_date(date_b, account_id)
        diff = leads_b - leads_a
        pct = 0 if leads_a == 0 else round((diff / leads_a) * 100, 2)
        return {
            'date_a': str(date_a),
            'date_b': str(date_b),
            'leads_a': leads_a,
            'leads_b': leads_b,
            'difference': diff,
            'percentage_change': pct,
        }

    def ranking_by_period(self, start_date: date, end_date: date, account_id: int | None = None) -> list[dict]:
        start, end = self._period_range(start_date, end_date)
        stmt = (
            select(
                GHLAccount.id,
                GHLAccount.name,
                func.count(Opportunity.id).label('leads_count'),
            )
            .join(Opportunity, Opportunity.account_id == GHLAccount.id, isouter=True)
            .where(
                Opportunity.ghl_created_at >= start,
                Opportunity.ghl_created_at < end,
                GHLAccount.active.is_(True),
            )
            .group_by(GHLAccount.id, GHLAccount.name)
            .order_by(func.count(Opportunity.id).desc())
        )
        if account_id:
            stmt = stmt.where(GHLAccount.id == account_id)
        return [
            {'account_id': row.id, 'account': row.name, 'leads_count': int(row.leads_count)}
            for row in self.db.execute(stmt)
        ]

    def performance_by_period(self, start_date: date, end_date: date, account_id: int | None = None) -> dict:
        start, end = self._period_range(start_date, end_date)

        opportunities = list(self.db.scalars(
            self._active_account_filter(Opportunity, account_id).where(
                Opportunity.ghl_created_at >= start,
                Opportunity.ghl_created_at < end,
            )
        ))
        sales = [item for item in opportunities if (item.status or '').lower() in SALE_STATUSES]

        lead_channels = Counter()
        hsm_leads = Counter()
        for opportunity in opportunities:
            channel = self._opportunity_channel(opportunity)
            if channel:
                lead_channels[channel] += 1
            if self._has_hsm(self._tags_from_opportunity(opportunity)):
                hsm_leads[channel or 'SEM CANAL'] += 1

        sales_channels = Counter()
        hsm_sales = Counter()
        for opportunity in sales:
            channel = self._opportunity_channel(opportunity)
            if channel:
                sales_channels[channel] += 1
            if self._has_hsm(self._tags_from_opportunity(opportunity)):
                hsm_sales[channel or 'SEM CANAL'] += 1

        opportunity_contact_ids = {item.contact_id for item in opportunities if item.contact_id}
        sales_contact_ids = {item.contact_id for item in sales if item.contact_id}
        lost_opportunities = [item for item in opportunities if (item.status or '').lower() == 'lost']
        lost_contact_ids = {item.contact_id for item in lost_opportunities if item.contact_id}

        funnel_counts = {
            'lead_novo': len(opportunities),
            'triagem_ia': sum(1 for item in opportunities if self._has_tag(self._tags_from_opportunity(item), 'triagem ia')),
            'triagem_finalizada': sum(
                1 for item in opportunities if self._has_tag(self._tags_from_opportunity(item), 'triagem ia finalizada')
            ),
            'em_atendimento': sum(1 for item in opportunities if self._has_attendance(self._tags_from_opportunity(item))),
            'hsm_enviado': sum(1 for item in opportunities if self._has_hsm(self._tags_from_opportunity(item))),
            'oportunidade_criada': len(opportunity_contact_ids),
            'venda_realizada': len(sales_contact_ids),
            'perdido': len(lost_contact_ids),
        }

        daily = Counter(self._local_date(item.ghl_created_at).isoformat() for item in opportunities)
        days = (end_date - start_date).days + 1
        daily_new_leads = [
            {
                'date': (start_date + timedelta(days=offset)).isoformat(),
                'leads': int(daily[(start_date + timedelta(days=offset)).isoformat()]),
            }
            for offset in range(days)
        ]

        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'account_id': account_id,
            'totals': {
                'new_leads': len(opportunities),
                'new_leads_with_channel': sum(lead_channels.values()),
                'sales': len(sales),
                'hsm_sales': sum(hsm_sales.values()),
                'hsm_leads': sum(hsm_leads.values()),
                'whatsapp_contacts': self._whatsapp_contacts_for_account(account_id, start_date, end_date) if account_id else 0,
                'inbox_conversations': self._inbox_conversations_for_account(account_id, start_date, end_date) if account_id else 0,
            },
            'daily_new_leads': daily_new_leads,
            'funnel_counts': funnel_counts,
            'lead_channels': [{'channel': channel, 'count': int(lead_channels[channel])} for channel in CHANNELS],
            'sales_channels': [{'channel': channel, 'count': int(sales_channels[channel])} for channel in CHANNELS],
            'hsm_sales_channels': [{'channel': channel, 'count': int(hsm_sales[channel])} for channel in CHANNELS],
        }

    def _account_summary(self, account: GHLAccount, start_date: date, end_date: date) -> dict:
        performance = self.performance_by_period(start_date, end_date, account.id)
        totals = performance['totals']
        lead_channels = {item['channel']: item['count'] for item in performance['lead_channels']}
        best_channel = max(lead_channels.items(), key=lambda item: item[1])[0] if any(lead_channels.values()) else '-'

        return {
            'account_id': account.id,
            'account': account.name,
            'new_leads': totals['new_leads'],
            'new_leads_with_channel': totals['new_leads_with_channel'],
            'attendances': self._attendances_for_account(account.id, start_date, end_date),
            'whatsapp_contacts': self._whatsapp_contacts_for_account(account.id, start_date, end_date),
            'inbox_conversations': self._inbox_conversations_for_account(account.id, start_date, end_date),
            'sales': totals['sales'],
            'hsm_leads': totals['hsm_leads'],
            'hsm_sales': totals['hsm_sales'],
            'lead_channels': performance['lead_channels'],
            'daily_new_leads': performance['daily_new_leads'],
            'daily_inbox_conversations': self._daily_inbox_conversations(account.id, start_date, end_date),
            'best_channel': best_channel,
        }

    def _attendances_for_account(self, account_id: int, start_date: date, end_date: date) -> int:
        start, end = self._period_range(start_date, end_date)
        opportunities = list(self.db.scalars(
            select(Opportunity).where(
                Opportunity.account_id == account_id,
                Opportunity.ghl_created_at >= start,
                Opportunity.ghl_created_at < end,
            )
        ))
        return sum(1 for item in opportunities if self._has_attendance(self._tags_from_opportunity(item)))

    def _whatsapp_contacts_for_account(self, account_id: int, start_date: date, end_date: date) -> int:
        start, end = self._period_range(start_date, end_date)
        conversations = list(self.db.scalars(
            select(Conversation).where(
                Conversation.account_id == account_id,
                Conversation.last_inbound_whatsapp_message_date >= start,
                Conversation.last_inbound_whatsapp_message_date < end,
            )
        ))
        identifiers = {
            item.contact_id or item.phone or item.ghl_conversation_id
            for item in conversations
            if item.contact_id or item.phone or item.ghl_conversation_id
        }
        return len(identifiers)

    def _conversation_entry_date(self, conversation: Conversation) -> datetime | None:
        return conversation.last_message_date or conversation.last_inbound_whatsapp_message_date

    def _inbox_conversations_for_account(self, account_id: int, start_date: date, end_date: date) -> int:
        start, end = self._period_range(start_date, end_date)
        conversations = list(self.db.scalars(
            select(Conversation).where(
                Conversation.account_id == account_id,
            )
        ))
        return sum(
            1
            for item in conversations
            if (entry_date := self._conversation_entry_date(item)) and entry_date >= start and entry_date < end
        )

    def _daily_inbox_conversations(self, account_id: int, start_date: date, end_date: date) -> list[dict]:
        start, end = self._period_range(start_date, end_date)
        conversations = list(self.db.scalars(
            select(Conversation).where(
                Conversation.account_id == account_id,
            )
        ))
        daily = Counter()
        for item in conversations:
            entry_date = self._conversation_entry_date(item)
            if entry_date and entry_date >= start and entry_date < end:
                daily[self._local_date(entry_date).isoformat()] += 1

        days = (end_date - start_date).days + 1
        return [
            {
                'date': (start_date + timedelta(days=offset)).isoformat(),
                'conversations': int(daily[(start_date + timedelta(days=offset)).isoformat()]),
            }
            for offset in range(days)
        ]

    def _rows_for_period(self, start_date: date, end_date: date) -> list[dict]:
        accounts = list(self.db.scalars(
            select(GHLAccount).where(GHLAccount.active.is_(True)).order_by(GHLAccount.name)
        ))
        rows = []
        for account in accounts:
            summary = self._account_summary(account, start_date, end_date)
            summary['attendance_rate'] = self._percent(summary['attendances'], summary['new_leads'])
            summary['sales_rate'] = self._percent(summary['sales'], summary['new_leads'])
            summary['channel_identified_rate'] = self._percent(summary['new_leads_with_channel'], summary['new_leads'])
            rows.append(summary)
        return rows

    def _rankings(self, rows: list[dict]) -> dict:
        metrics = {
            'new_leads': 'Leads',
            'whatsapp_contacts': 'WhatsApp',
            'inbox_conversations': 'Conversas na caixa',
            'attendances': 'Atendimentos',
            'sales': 'Vendas',
            'attendance_rate': 'Conversao em atendimento',
            'sales_rate': 'Conversao em venda',
            'channel_identified_rate': 'Canais identificados',
            'health_score': 'Saude operacional',
        }
        return {
            key: {
                'label': label,
                'best': sorted(rows, key=lambda item: item[key], reverse=True),
                'worst': sorted(rows, key=lambda item: item[key]),
            }
            for key, label in metrics.items()
        }

    def _highlights(self, rows: list[dict], previous_rows: list[dict]) -> dict:
        if not rows:
            return {}

        previous_by_account = {row['account_id']: row for row in previous_rows}
        growth_rows = [
            {
                **row,
                'lead_delta': row['new_leads'] - previous_by_account.get(row['account_id'], {}).get('new_leads', 0),
                'whatsapp_delta': row['whatsapp_contacts'] - previous_by_account.get(row['account_id'], {}).get('whatsapp_contacts', 0),
                'inbox_conversation_delta': row['inbox_conversations'] - previous_by_account.get(row['account_id'], {}).get('inbox_conversations', 0),
            }
            for row in rows
        ]

        return {
            'most_leads': max(rows, key=lambda item: item['new_leads']),
            'least_leads': min(rows, key=lambda item: item['new_leads']),
            'most_whatsapp': max(rows, key=lambda item: item['whatsapp_contacts']),
            'most_inbox_conversations': max(rows, key=lambda item: item['inbox_conversations']),
            'least_whatsapp': min(rows, key=lambda item: item['whatsapp_contacts']),
            'most_attendances': max(rows, key=lambda item: item['attendances']),
            'least_attendances': min(rows, key=lambda item: item['attendances']),
            'most_sales': max(rows, key=lambda item: item['sales']),
            'best_attendance_rate': max(rows, key=lambda item: item['attendance_rate']),
            'best_channel_rate': max(rows, key=lambda item: item['channel_identified_rate']),
            'biggest_growth': max(growth_rows, key=lambda item: item['lead_delta']),
            'biggest_drop': min(growth_rows, key=lambda item: item['lead_delta']),
            'biggest_whatsapp_growth': max(growth_rows, key=lambda item: item['whatsapp_delta']),
            'biggest_inbox_conversation_growth': max(growth_rows, key=lambda item: item['inbox_conversation_delta']),
        }

    def _channel_comparison(self, rows: list[dict]) -> list[dict]:
        comparison = []
        for row in rows:
            channel_counts = {item['channel']: item['count'] for item in row['lead_channels']}
            for channel in CHANNELS:
                comparison.append({
                    'account': row['account'],
                    'channel': channel,
                    'leads': int(channel_counts.get(channel, 0)),
                })
        return comparison

    def _daily_by_account(self, rows: list[dict]) -> list[dict]:
        daily = []
        for row in rows:
            for item in row['daily_new_leads']:
                daily.append({
                    'account': row['account'],
                    'date': item['date'],
                    'leads': item['leads'],
                })
        return daily

    def _daily_conversations_by_account(self, rows: list[dict]) -> list[dict]:
        daily = []
        for row in rows:
            for item in row['daily_inbox_conversations']:
                daily.append({
                    'account': row['account'],
                    'date': item['date'],
                    'conversations': item['conversations'],
                })
        return daily

    def _weekday_heatmap(self, rows: list[dict]) -> list[dict]:
        totals: dict[tuple[str, int], int] = {}
        for row in rows:
            for item in row['daily_new_leads']:
                target = date.fromisoformat(item['date'])
                key = (row['account'], target.weekday())
                totals[key] = totals.get(key, 0) + int(item['leads'])

        heatmap = []
        for row in rows:
            for index, weekday in enumerate(WEEKDAYS):
                heatmap.append({
                    'account': row['account'],
                    'weekday': weekday,
                    'weekday_index': index,
                    'leads': totals.get((row['account'], index), 0),
                })
        return heatmap

    def _last_sync_at(self) -> str | None:
        values = [
            self.db.scalar(select(func.max(Lead.synced_at))),
            self.db.scalar(select(func.max(Opportunity.synced_at))),
            self.db.scalar(select(func.max(Conversation.synced_at))),
        ]
        latest = max((value for value in values if value), default=None)
        if not latest:
            return None
        return latest.replace(tzinfo=timezone.utc).astimezone(LOCAL_TIMEZONE).isoformat()

    def _health_score(self, row: dict, previous: dict) -> int:
        lead_change = self._change_percent(row['new_leads'], previous.get('new_leads', 0))
        score = 0
        score += min(30, row['attendance_rate'] * 0.3)
        score += min(20, row['channel_identified_rate'] * 0.2)
        score += min(15, row['sales_rate'] * 1.5)
        score += min(15, self._percent(row['whatsapp_contacts'], row['new_leads']) * 0.15)
        score += 10 if row['new_leads'] > 0 else 0
        score += max(-20, min(10, lead_change / 5))
        return int(max(0, min(100, round(score))))

    def _executive_summary(self, rows: list[dict], previous_rows: list[dict]) -> str:
        if not rows:
            return 'Sem dados suficientes para gerar o resumo executivo.'

        previous_by_account = {row['account_id']: row for row in previous_rows}
        total_leads = sum(row['new_leads'] for row in rows)
        total_previous = sum(previous_by_account.get(row['account_id'], {}).get('new_leads', 0) for row in rows)
        total_whatsapp = sum(row['whatsapp_contacts'] for row in rows)
        total_inbox_conversations = sum(row['inbox_conversations'] for row in rows)
        total_sales = sum(row['sales'] for row in rows)
        lead_delta = total_leads - total_previous
        lead_winner = max(rows, key=lambda item: item['new_leads'])
        whatsapp_winner = max(rows, key=lambda item: item['whatsapp_contacts'])
        health_winner = max(rows, key=lambda item: item.get('health_score', 0))
        health_attention = min(rows, key=lambda item: item.get('health_score', 0))

        return (
            f"No periodo selecionado, as revistas somaram {total_leads} leads "
            f"({lead_delta:+d} vs periodo anterior), {total_inbox_conversations} conversas na caixa, "
            f"{total_whatsapp} pessoas no WhatsApp e {total_sales} vendas. "
            f"{lead_winner['account']} liderou em leads com {lead_winner['new_leads']}. "
            f"{whatsapp_winner['account']} liderou no WhatsApp com {whatsapp_winner['whatsapp_contacts']} contatos. "
            f"O melhor score operacional foi de {health_winner['account']} ({health_winner.get('health_score', 0)}/100). "
            f"O principal ponto de atencao e {health_attention['account']} ({health_attention.get('health_score', 0)}/100)."
        )

    def _alerts(self, rows: list[dict], previous_rows: list[dict]) -> list[dict]:
        alerts = []
        previous_by_account = {row['account_id']: row for row in previous_rows}
        avg_attendance = sum(row['attendance_rate'] for row in rows) / len(rows) if rows else 0

        for row in rows:
            previous = previous_by_account.get(row['account_id'], {})
            lead_change = self._change_percent(row['new_leads'], previous.get('new_leads', 0))
            if lead_change <= -20:
                alerts.append({
                    'type': 'queda',
                    'account': row['account'],
                    'message': f"{row['account']} caiu {abs(lead_change)}% em novos leads vs periodo anterior.",
                })
            if row['channel_identified_rate'] < 70:
                alerts.append({
                    'type': 'canal',
                    'account': row['account'],
                    'message': f"{row['account']} tem apenas {row['channel_identified_rate']}% dos leads com canal identificado.",
                })
            if row['attendance_rate'] < avg_attendance:
                alerts.append({
                    'type': 'atendimento',
                    'account': row['account'],
                    'message': f"{row['account']} esta abaixo da media de atendimento ({row['attendance_rate']}%).",
                })
            if row['sales'] == 0:
                alerts.append({
                    'type': 'vendas',
                    'account': row['account'],
                    'message': f"{row['account']} nao teve vendas no periodo selecionado.",
                })
        return alerts

    def _diagnosis(self, rows: list[dict], previous_rows: list[dict]) -> str:
        if not rows:
            return 'Nao ha dados suficientes para diagnostico no periodo selecionado.'

        previous_by_account = {row['account_id']: row for row in previous_rows}
        lead_winner = max(rows, key=lambda item: item['new_leads'])
        attendance_winner = max(rows, key=lambda item: item['attendances'])
        sales_winner = max(rows, key=lambda item: item['sales'])
        weakest = min(rows, key=lambda item: item['new_leads'])
        growth_rows = [
            {
                **row,
                'lead_delta': row['new_leads'] - previous_by_account.get(row['account_id'], {}).get('new_leads', 0),
                'whatsapp_delta': row['whatsapp_contacts'] - previous_by_account.get(row['account_id'], {}).get('whatsapp_contacts', 0),
                'lead_change_percent': self._change_percent(
                    row['new_leads'],
                    previous_by_account.get(row['account_id'], {}).get('new_leads', 0),
                ),
            }
            for row in rows
        ]
        growth_winner = max(growth_rows, key=lambda item: item['lead_change_percent'])
        biggest_drop = min(growth_rows, key=lambda item: item['lead_delta'])
        whatsapp_winner = max(rows, key=lambda item: item['whatsapp_contacts'])
        inbox_winner = max(rows, key=lambda item: item['inbox_conversations'])
        channel_leader = max(rows, key=lambda item: item['channel_identified_rate'])

        return (
            f"{lead_winner['account']} liderou em novos leads com {lead_winner['new_leads']}. "
            f"{inbox_winner['account']} teve mais conversas na caixa ({inbox_winner['inbox_conversations']}). "
            f"{whatsapp_winner['account']} teve mais pessoas no WhatsApp ({whatsapp_winner['whatsapp_contacts']}). "
            f"{attendance_winner['account']} teve mais atendimentos ({attendance_winner['attendances']}). "
            f"{sales_winner['account']} liderou em vendas ({sales_winner['sales']}). "
            f"{growth_winner['account']} teve a maior variacao vs periodo anterior ({growth_winner['lead_change_percent']}%). "
            f"{channel_leader['account']} ficou com melhor identificacao de canal ({channel_leader['channel_identified_rate']}%). "
            f"{weakest['account']} ficou com o menor volume de leads ({weakest['new_leads']}). "
            f"{biggest_drop['account']} foi o principal ponto de atencao em queda absoluta ({biggest_drop['lead_delta']} leads)."
        )

    def executive_dashboard(self, start_date: date, end_date: date) -> dict:
        previous_start, previous_end = self._previous_period(start_date, end_date)
        rows = self._rows_for_period(start_date, end_date)
        previous_rows = self._rows_for_period(previous_start, previous_end)
        previous_by_account = {row['account_id']: row for row in previous_rows}

        table_rows = []
        for row in rows:
            previous = previous_by_account.get(row['account_id'], {})
            lead_change = self._change_percent(row['new_leads'], previous.get('new_leads', 0))
            attendance_change = self._change_percent(row['attendances'], previous.get('attendances', 0))
            health_score = self._health_score(row, previous)
            table_rows.append({
                'account_id': row['account_id'],
                'account': row['account'],
                'new_leads': row['new_leads'],
                'previous_new_leads': previous.get('new_leads', 0),
                'lead_change_percent': lead_change,
                'attendances': row['attendances'],
                'previous_attendances': previous.get('attendances', 0),
                'attendance_change_percent': attendance_change,
                'whatsapp_contacts': row['whatsapp_contacts'],
                'previous_whatsapp_contacts': previous.get('whatsapp_contacts', 0),
                'whatsapp_change_percent': self._change_percent(
                    row['whatsapp_contacts'],
                    previous.get('whatsapp_contacts', 0),
                ),
                'inbox_conversations': row['inbox_conversations'],
                'previous_inbox_conversations': previous.get('inbox_conversations', 0),
                'inbox_conversation_change_percent': self._change_percent(
                    row['inbox_conversations'],
                    previous.get('inbox_conversations', 0),
                ),
                'sales': row['sales'],
                'previous_sales': previous.get('sales', 0),
                'new_leads_with_channel': row['new_leads_with_channel'],
                'attendance_rate': row['attendance_rate'],
                'sales_rate': row['sales_rate'],
                'channel_identified_rate': row['channel_identified_rate'],
                'hsm_leads': row['hsm_leads'],
                'best_channel': row['best_channel'],
                'health_score': health_score,
            })

        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'previous_start_date': previous_start.isoformat(),
            'previous_end_date': previous_end.isoformat(),
            'rows': table_rows,
            'totals': {
                'new_leads': sum(row['new_leads'] for row in table_rows),
                'previous_new_leads': sum(row['previous_new_leads'] for row in table_rows),
                'whatsapp_contacts': sum(row['whatsapp_contacts'] for row in table_rows),
                'previous_whatsapp_contacts': sum(row['previous_whatsapp_contacts'] for row in table_rows),
                'inbox_conversations': sum(row['inbox_conversations'] for row in table_rows),
                'previous_inbox_conversations': sum(row['previous_inbox_conversations'] for row in table_rows),
                'attendances': sum(row['attendances'] for row in table_rows),
                'previous_attendances': sum(row['previous_attendances'] for row in table_rows),
                'sales': sum(row['sales'] for row in table_rows),
                'previous_sales': sum(row['previous_sales'] for row in table_rows),
            },
            'rankings': self._rankings(table_rows),
            'highlights': self._highlights(table_rows, previous_rows),
            'channel_comparison': self._channel_comparison(rows),
            'daily_by_account': self._daily_by_account(rows),
            'daily_conversations_by_account': self._daily_conversations_by_account(rows),
            'weekday_heatmap': self._weekday_heatmap(rows),
            'alerts': self._alerts(table_rows, previous_rows),
            'diagnosis': self._diagnosis(table_rows, previous_rows),
            'executive_summary': self._executive_summary(table_rows, previous_rows),
            'last_sync_at': self._last_sync_at(),
        }

    def build_daily_snapshots(self, start_date: date, end_date: date) -> dict:
        accounts = list(self.db.scalars(select(GHLAccount).where(GHLAccount.active.is_(True))))
        count = 0
        days = (end_date - start_date).days + 1

        for offset in range(days):
            target_date = start_date + timedelta(days=offset)
            for account in accounts:
                performance = self.performance_by_period(target_date, target_date, account.id)
                totals = performance['totals']
                attendances = self._attendances_for_account(account.id, target_date, target_date)
                values = {
                    'snapshot_date': target_date,
                    'account_id': account.id,
                    'account_name': account.name,
                    'new_leads': totals['new_leads'],
                    'new_leads_with_channel': totals['new_leads_with_channel'],
                    'attendances': attendances,
                    'sales': totals['sales'],
                    'hsm_leads': totals['hsm_leads'],
                    'attendance_rate': self._percent(attendances, totals['new_leads']),
                    'sales_rate': self._percent(totals['sales'], totals['new_leads']),
                    'channel_identified_rate': self._percent(totals['new_leads_with_channel'], totals['new_leads']),
                }
                stmt = self._insert(DailySnapshot).values(**values)
                update_values = {key: value for key, value in values.items() if key not in {'snapshot_date', 'account_id'}}
                if self.db.bind and self.db.bind.dialect.name == 'sqlite':
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['snapshot_date', 'account_id'],
                        set_=update_values,
                    )
                else:
                    stmt = stmt.on_conflict_do_update(
                        constraint='uq_daily_snapshot_account_date',
                        set_=update_values,
                    )
                self.db.execute(stmt)
                count += 1

        self.db.commit()
        return {'snapshots_created_or_updated': count, 'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}

    def list_daily_snapshots(self, start_date: date, end_date: date, account_id: int | None = None) -> list[dict]:
        stmt = (
            select(DailySnapshot)
            .where(DailySnapshot.snapshot_date >= start_date, DailySnapshot.snapshot_date <= end_date)
            .order_by(DailySnapshot.snapshot_date, DailySnapshot.account_name)
        )
        if account_id:
            stmt = stmt.where(DailySnapshot.account_id == account_id)

        rows = list(self.db.scalars(stmt))
        return [
            {
                'date': row.snapshot_date.isoformat(),
                'account_id': row.account_id,
                'account': row.account_name,
                'new_leads': row.new_leads,
                'new_leads_with_channel': row.new_leads_with_channel,
                'attendances': row.attendances,
                'sales': row.sales,
                'hsm_leads': row.hsm_leads,
                'attendance_rate': float(row.attendance_rate),
                'sales_rate': float(row.sales_rate),
                'channel_identified_rate': float(row.channel_identified_rate),
            }
            for row in rows
        ]

    def comparison_by_period(self, start_date: date, end_date: date) -> dict:
        accounts = list(self.db.scalars(
            select(GHLAccount).where(GHLAccount.active.is_(True)).order_by(GHLAccount.name)
        ))
        rows = []
        start, end = self._period_range(start_date, end_date)

        for account in accounts:
            performance = self.performance_by_period(start_date, end_date, account.id)
            totals = performance['totals']
            rows.append({
                'account_id': account.id,
                'account': account.name,
                'new_leads': totals['new_leads'],
                'new_leads_with_channel': totals['new_leads_with_channel'],
                'attendances': self._attendances_for_account(account.id, start_date, end_date),
                'sales': totals['sales'],
                'hsm_leads': totals['hsm_leads'],
                'hsm_sales': totals['hsm_sales'],
            })

        sorted_by_attendance = sorted(rows, key=lambda item: item['attendances'], reverse=True)
        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'rows': rows,
            'most_attendances': sorted_by_attendance[0] if sorted_by_attendance else None,
            'least_attendances': sorted_by_attendance[-1] if sorted_by_attendance else None,
        }
