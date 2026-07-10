import unicodedata
import logging
from datetime import datetime, time, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.security import decrypt_token
from app.integrations.ghl.client import GHLClient
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.opportunity import Opportunity
from app.models.sync_history import SyncHistory
from app.repositories.account_repository import AccountRepository
from app.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)
INCREMENTAL_SYNC_DAYS = 2
HISTORY_SYNC_DAYS = 3650
SNAPSHOT_SYNC_DAYS = 90
LOCAL_TIMEZONE = ZoneInfo('America/Sao_Paulo')


class GHLSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)

    async def sync_all(
        self,
        days_back: int = INCREMENTAL_SYNC_DAYS,
        account_ids: list[int] | None = None,
        history_once: bool = False,
    ) -> dict:
        result = {
            'accounts': 0,
            'accounts_skipped': 0,
            'leads_inserted_or_updated': 0,
            'opportunities_inserted_or_updated': 0,
            'conversations_inserted_or_updated': 0,
            'snapshots_created_or_updated': 0,
            'account_results': [],
            'errors': [],
            'history_once': history_once,
        }
        days_back = HISTORY_SYNC_DAYS if history_once else days_back
        start_date = self._sync_start_datetime(days_back)
        allowed_account_ids = set(account_ids or [])
        accounts = self.accounts.list_active()
        if allowed_account_ids:
            accounts = [account for account in accounts if account.id in allowed_account_ids]

        for account in accounts:
            account_result = {
                'account_id': account.id,
                'account': account.name,
                'leads': 0,
                'opportunities': 0,
                'conversations': 0,
                'status': 'ok',
            }
            try:
                if history_once and self._historical_sync_completed(account.id):
                    account_result['status'] = 'skipped'
                    account_result['skipped_reason'] = 'Historico ja carregado'
                    result['accounts_skipped'] += 1
                    result['account_results'].append(account_result)
                    continue

                token = decrypt_token(account.api_token_encrypted)
                client = GHLClient(token)

                leads = await self._fetch_contacts(client, account.location_id, start_date)
                account_result['leads'] = self._upsert_leads(account.id, leads)
                result['leads_inserted_or_updated'] += account_result['leads']

                pipeline_stages = await self._fetch_pipeline_stages(client, account.location_id)
                opportunities = await self._fetch_opportunities(client, account.location_id, start_date, pipeline_stages)
                account_result['opportunities'] = self._upsert_opportunities(account.id, opportunities)
                result['opportunities_inserted_or_updated'] += account_result['opportunities']

                conversations = await self._fetch_conversations(client, account.location_id, start_date)
                account_result['conversations'] = self._upsert_conversations(account.id, conversations)
                result['conversations_inserted_or_updated'] += account_result['conversations']
                if history_once:
                    self._mark_historical_sync_completed(account.id, days_back)
                result['accounts'] += 1
            except Exception as exc:
                self.db.rollback()
                account_result['status'] = 'error'
                account_result['error'] = str(exc)
                result['errors'].append({'account': account.name, 'error': str(exc)})

            result['account_results'].append(account_result)

        if not result['account_results']:
            result['errors'].append({'account': None, 'error': 'Nenhuma revista ativa selecionada.'})
        elif result['accounts']:
            snapshot_start_date = max(
                start_date.date(),
                (datetime.utcnow() - timedelta(days=SNAPSHOT_SYNC_DAYS)).date(),
            )
            snapshots = MetricsService(self.db).build_daily_snapshots(
                snapshot_start_date,
                datetime.utcnow().date(),
                [item['account_id'] for item in result['account_results'] if item['status'] == 'ok'],
            )
            result['snapshots_created_or_updated'] = snapshots['snapshots_created_or_updated']
        return result

    def _historical_sync_completed(self, account_id: int) -> bool:
        return bool(self.db.scalar(
            select(SyncHistory.id).where(
                SyncHistory.account_id == account_id,
                SyncHistory.sync_type == 'historical',
                SyncHistory.completed_at.is_not(None),
            )
        ))

    def _mark_historical_sync_completed(self, account_id: int, days_back: int) -> None:
        existing = self.db.scalar(
            select(SyncHistory).where(
                SyncHistory.account_id == account_id,
                SyncHistory.sync_type == 'historical',
            )
        )
        if existing:
            existing.days_back = days_back
            existing.completed_at = datetime.utcnow()
        else:
            self.db.add(SyncHistory(
                account_id=account_id,
                sync_type='historical',
                days_back=days_back,
                completed_at=datetime.utcnow(),
            ))
        self.db.commit()

    def _sync_start_datetime(self, days_back: int) -> datetime:
        if days_back >= HISTORY_SYNC_DAYS:
            return datetime.utcnow() - timedelta(days=days_back)
        local_start_date = datetime.now(LOCAL_TIMEZONE).date() - timedelta(days=days_back)
        local_start = datetime.combine(local_start_date, time.min, tzinfo=LOCAL_TIMEZONE)
        return local_start.astimezone(timezone.utc).replace(tzinfo=None)

    def _advance_pagination(self, params: dict, meta: dict, seen_cursors: set[tuple[str, str]]) -> bool:
        start_after = meta.get('startAfter')
        start_after_id = meta.get('startAfterId')
        if start_after and start_after_id:
            cursor = (str(start_after), str(start_after_id))
            if cursor in seen_cursors:
                return False
            seen_cursors.add(cursor)
            params['startAfter'] = start_after
            params['startAfterId'] = start_after_id
            return True

        next_page_url = meta.get('nextPageUrl') or meta.get('nextPage')
        if not next_page_url:
            return False

        parsed = urlparse(str(next_page_url))
        query = parse_qs(parsed.query)
        next_start_after = query.get('startAfter', [None])[0]
        next_start_after_id = query.get('startAfterId', [None])[0]
        if not next_start_after or not next_start_after_id:
            return False

        cursor = (str(next_start_after), str(next_start_after_id))
        if cursor in seen_cursors:
            return False
        seen_cursors.add(cursor)
        params['startAfter'] = next_start_after
        params['startAfterId'] = next_start_after_id
        return True

    async def _fetch_contacts(self, client: GHLClient, location_id: str, start_date: datetime) -> list[dict]:
        contacts: list[dict] = []
        page = 1
        page_limit = 50
        start_value = start_date.isoformat() + 'Z'

        while True:
            data = await client.post('/contacts/search', {
                'locationId': location_id,
                'page': page,
                'pageLimit': page_limit,
                'filters': [
                    {
                        'field': 'dateAdded',
                        'operator': 'range',
                        'value': {'gte': start_value},
                    },
                ],
            })
            page_contacts = data.get('contacts', [])
            for item in page_contacts:
                created_at = self._parse_date(item.get('dateAdded') or item.get('createdAt'))
                if created_at >= start_date:
                    contacts.append(item)

            if not page_contacts:
                break

            total = int(data.get('total') or len(contacts))
            if page * page_limit >= total:
                break
            page += 1

        return contacts

    async def _fetch_pipeline_stages(self, client: GHLClient, location_id: str) -> dict[str, dict[str, str | None]]:
        try:
            data = await client.get('/opportunities/pipelines', params={'locationId': location_id})
        except Exception:
            logger.exception('Falha ao buscar pipelines do GHL')
            return {}

        stage_lookup: dict[str, dict[str, str | None]] = {}
        for pipeline in data.get('pipelines') or []:
            pipeline_id = pipeline.get('id') or pipeline.get('_id')
            pipeline_name = pipeline.get('name')
            for stage in pipeline.get('stages') or []:
                stage_id = stage.get('id') or stage.get('_id') or stage.get('stageId')
                if not stage_id:
                    continue
                stage_lookup[str(stage_id)] = {
                    'pipeline_id': pipeline_id,
                    'pipeline_name': pipeline_name,
                    'stage_name': stage.get('name'),
                }
        return stage_lookup

    async def _fetch_opportunities(
        self,
        client: GHLClient,
        location_id: str,
        start_date: datetime,
        pipeline_stages: dict[str, dict[str, str | None]] | None = None,
    ) -> list[dict]:
        opportunities: list[dict] = []
        params = {'location_id': location_id, 'limit': 100}
        pipeline_stages = pipeline_stages or {}
        seen_cursors: set[tuple[str, str]] = set()

        while True:
            data = await client.get('/opportunities/search', params=params)
            page_opportunities = data.get('opportunities', [])
            for item in page_opportunities:
                created_at = self._parse_date(item.get('createdAt') or item.get('dateAdded'))
                if created_at >= start_date:
                    stage_data = pipeline_stages.get(str(item.get('pipelineStageId') or ''))
                    if stage_data:
                        item = {
                            **item,
                            '_pipelineName': stage_data.get('pipeline_name'),
                            '_pipelineStageName': stage_data.get('stage_name'),
                        }
                    opportunities.append(item)

            if not page_opportunities:
                break

            meta = data.get('meta') or {}
            if not self._advance_pagination(params, meta, seen_cursors):
                break

        return opportunities

    async def _fetch_conversations(
        self,
        client: GHLClient,
        location_id: str,
        start_date: datetime | None = None,
    ) -> list[dict]:
        conversations: list[dict] = []
        params = {'locationId': location_id, 'limit': 100}
        seen_ids: set[str] = set()
        seen_cursors: set[tuple[str, str]] = set()
        seen_date_cursors: set[str] = set()

        while True:
            data = await client.get('/conversations/search', params=params)
            page_conversations = data.get('conversations', [])
            if not page_conversations:
                break

            reached_cutoff = False
            added_before_page = len(conversations)
            for item in page_conversations:
                conversation_id = str(item.get('id') or '')
                if not conversation_id or conversation_id in seen_ids:
                    continue

                last_message_date = self._parse_timestamp_ms(item.get('lastMessageDate'))
                last_inbound_date = self._parse_timestamp_ms(item.get('lastInboundWhatsappMessageDate'))
                newest_activity = max(
                    [value for value in [last_message_date, last_inbound_date] if value],
                    default=None,
                )
                if start_date and newest_activity and newest_activity < start_date:
                    reached_cutoff = True
                    continue

                seen_ids.add(conversation_id)
                conversations.append(item)

            if len(conversations) == added_before_page:
                break

            meta = data.get('meta') or {}
            if self._advance_pagination(params, meta, seen_cursors):
                params.pop('startAfterDate', None)
                continue

            cursor = page_conversations[-1].get('lastMessageDate')
            if not cursor:
                break
            cursor = str(cursor)
            if cursor in seen_date_cursors:
                break
            seen_date_cursors.add(cursor)

            params['startAfterDate'] = cursor

        return conversations

    def _parse_date(self, value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)

    def _parse_timestamp_ms(self, value: int | str | None) -> datetime | None:
        if not value:
            return None
        if isinstance(value, str):
            if value.isdigit():
                value = int(value)
            else:
                return self._parse_date(value)
        return datetime.utcfromtimestamp(value / 1000)

    def _clean_text(self, value: str | None) -> str:
        normalized = unicodedata.normalize('NFKD', value or '')
        return normalized.encode('ascii', 'ignore').decode().lower()

    def _source_from_tags(self, tags: list[str] | None) -> str | None:
        for tag in tags or []:
            clean = self._clean_text(str(tag))
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

    def _opportunity_tags(self, item: dict) -> list[str]:
        tags = list((item.get('contact') or {}).get('tags') or [])
        for relation in item.get('relations') or []:
            for tag in relation.get('tags') or []:
                if tag not in tags:
                    tags.append(tag)
        return tags

    def _insert(self, model):
        if self._is_sqlite():
            return sqlite_insert(model)
        return insert(model)

    def _is_sqlite(self) -> bool:
        return bool(self.db.bind and self.db.bind.dialect.name == 'sqlite')

    def _lead_values(self, account_id: int, item: dict) -> dict:
        return {
            'ghl_contact_id': item.get('id') or item.get('contactId'),
            'account_id': account_id,
            'name': item.get('name') or item.get('contactName'),
            'email': item.get('email'),
            'phone': item.get('phone'),
            'source': item.get('source') or item.get('utmSource') or self._source_from_tags(item.get('tags')),
            'ghl_created_at': self._parse_date(item.get('dateAdded') or item.get('createdAt')),
            'synced_at': datetime.utcnow(),
            'raw_data': item,
        }

    def _opportunity_values(self, account_id: int, item: dict) -> dict:
        return {
            'ghl_opportunity_id': item.get('id'),
            'account_id': account_id,
            'contact_id': item.get('contactId'),
            'pipeline_id': item.get('pipelineId'),
            'pipeline_stage_id': item.get('pipelineStageId'),
            'status': item.get('status'),
            'monetary_value': item.get('monetaryValue'),
            'source': item.get('source') or self._source_from_tags(self._opportunity_tags(item)),
            'ghl_created_at': self._parse_date(item.get('createdAt') or item.get('dateAdded')),
            'synced_at': datetime.utcnow(),
            'raw_data': item,
        }

    def _conversation_values(self, account_id: int, item: dict) -> dict:
        return {
            'ghl_conversation_id': item.get('id'),
            'account_id': account_id,
            'contact_id': item.get('contactId'),
            'contact_name': item.get('contactName') or item.get('fullName'),
            'phone': item.get('phone'),
            'last_message_type': item.get('lastMessageType'),
            'last_message_direction': item.get('lastMessageDirection'),
            'last_message_date': self._parse_timestamp_ms(item.get('lastMessageDate')),
            'last_inbound_whatsapp_message_date': self._parse_timestamp_ms(item.get('lastInboundWhatsappMessageDate')),
            'synced_at': datetime.utcnow(),
            'raw_data': item,
        }

    def _upsert_leads(self, account_id: int, contacts: list[dict]) -> int:
        count = 0
        for item in contacts:
            values = self._lead_values(account_id, item)
            if not values['ghl_contact_id']:
                continue

            stmt = self._insert(Lead).values(**values)
            update_values = {
                'name': values['name'],
                'email': values['email'],
                'phone': values['phone'],
                'source': values['source'],
                'ghl_created_at': values['ghl_created_at'],
                'synced_at': values['synced_at'],
                'raw_data': values['raw_data'],
            }
            if self._is_sqlite():
                stmt = stmt.on_conflict_do_update(
                    index_elements=['ghl_contact_id', 'account_id'],
                    set_=update_values,
                )
            else:
                stmt = stmt.on_conflict_do_update(
                    constraint='uq_lead_contact_account',
                    set_=update_values,
                )
            self.db.execute(stmt)
            count += 1
        self.db.commit()
        return count

    def _upsert_opportunities(self, account_id: int, opportunities: list[dict]) -> int:
        count = 0
        for item in opportunities:
            values = self._opportunity_values(account_id, item)
            if not values['ghl_opportunity_id']:
                continue

            stmt = self._insert(Opportunity).values(**values)
            update_values = {
                'contact_id': values['contact_id'],
                'pipeline_id': values['pipeline_id'],
                'pipeline_stage_id': values['pipeline_stage_id'],
                'status': values['status'],
                'monetary_value': values['monetary_value'],
                'source': values['source'],
                'ghl_created_at': values['ghl_created_at'],
                'synced_at': values['synced_at'],
                'raw_data': values['raw_data'],
            }
            if self._is_sqlite():
                stmt = stmt.on_conflict_do_update(
                    index_elements=['ghl_opportunity_id', 'account_id'],
                    set_=update_values,
                )
            else:
                stmt = stmt.on_conflict_do_update(
                    constraint='uq_opportunity_account',
                    set_=update_values,
                )
            self.db.execute(stmt)
            count += 1
        self.db.commit()
        return count

    def _upsert_conversations(self, account_id: int, conversations: list[dict]) -> int:
        count = 0
        for item in conversations:
            values = self._conversation_values(account_id, item)
            if not values['ghl_conversation_id']:
                continue

            stmt = self._insert(Conversation).values(**values)
            update_values = {
                'contact_id': values['contact_id'],
                'contact_name': values['contact_name'],
                'phone': values['phone'],
                'last_message_type': values['last_message_type'],
                'last_message_direction': values['last_message_direction'],
                'last_message_date': values['last_message_date'],
                'last_inbound_whatsapp_message_date': values['last_inbound_whatsapp_message_date'],
                'synced_at': values['synced_at'],
                'raw_data': values['raw_data'],
            }
            if self._is_sqlite():
                stmt = stmt.on_conflict_do_update(
                    index_elements=['ghl_conversation_id', 'account_id'],
                    set_=update_values,
                )
            else:
                stmt = stmt.on_conflict_do_update(
                    constraint='uq_conversation_account',
                    set_=update_values,
                )
            self.db.execute(stmt)
            count += 1
        self.db.commit()
        return count
