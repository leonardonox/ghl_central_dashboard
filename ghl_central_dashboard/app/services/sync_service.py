import unicodedata
from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.security import decrypt_token
from app.integrations.ghl.client import GHLClient
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.opportunity import Opportunity
from app.repositories.account_repository import AccountRepository


class GHLSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)

    async def sync_all(self, days_back: int = 7) -> dict:
        result = {
            'accounts': 0,
            'leads_inserted_or_updated': 0,
            'opportunities_inserted_or_updated': 0,
            'conversations_inserted_or_updated': 0,
            'account_results': [],
            'errors': [],
        }
        for account in self.accounts.list_active():
            account_result = {
                'account_id': account.id,
                'account': account.name,
                'leads': 0,
                'opportunities': 0,
                'conversations': 0,
                'status': 'ok',
            }
            try:
                token = decrypt_token(account.api_token_encrypted)
                client = GHLClient(token)
                start_date = datetime.utcnow() - timedelta(days=days_back)

                leads = await self._fetch_contacts(client, account.location_id, start_date)
                account_result['leads'] = self._upsert_leads(account.id, leads)
                result['leads_inserted_or_updated'] += account_result['leads']

                opportunities = await self._fetch_opportunities(client, account.location_id, start_date)
                account_result['opportunities'] = self._upsert_opportunities(account.id, opportunities)
                result['opportunities_inserted_or_updated'] += account_result['opportunities']

                conversations = await self._fetch_conversations(client, account.location_id)
                account_result['conversations'] = self._upsert_conversations(account.id, conversations)
                result['conversations_inserted_or_updated'] += account_result['conversations']
                result['accounts'] += 1
            except Exception as exc:
                self.db.rollback()
                account_result['status'] = 'error'
                account_result['error'] = str(exc)
                result['errors'].append({'account': account.name, 'error': str(exc)})

            result['account_results'].append(account_result)

        if not result['account_results']:
            result['errors'].append({'account': None, 'error': 'Nenhuma revista ativa cadastrada.'})
        return result

    async def _fetch_contacts(self, client: GHLClient, location_id: str, start_date: datetime) -> list[dict]:
        contacts: list[dict] = []
        params = {'locationId': location_id, 'limit': 100}

        while True:
            data = await client.get('/contacts/', params=params)
            page_contacts = data.get('contacts', [])
            for item in page_contacts:
                created_at = self._parse_date(item.get('dateAdded') or item.get('createdAt'))
                if created_at >= start_date:
                    contacts.append(item)

            if not page_contacts:
                break

            oldest_in_page = min(
                self._parse_date(item.get('dateAdded') or item.get('createdAt'))
                for item in page_contacts
            )
            meta = data.get('meta') or {}
            if oldest_in_page < start_date or not meta.get('startAfter') or not meta.get('startAfterId'):
                break

            params['startAfter'] = meta['startAfter']
            params['startAfterId'] = meta['startAfterId']

        return contacts

    async def _fetch_opportunities(self, client: GHLClient, location_id: str, start_date: datetime) -> list[dict]:
        opportunities: list[dict] = []
        params = {'location_id': location_id, 'limit': 100}

        while True:
            data = await client.get('/opportunities/search', params=params)
            page_opportunities = data.get('opportunities', [])
            for item in page_opportunities:
                created_at = self._parse_date(item.get('createdAt') or item.get('dateAdded'))
                if created_at >= start_date:
                    opportunities.append(item)

            if not page_opportunities:
                break

            oldest_in_page = min(
                self._parse_date(item.get('createdAt') or item.get('dateAdded'))
                for item in page_opportunities
            )
            meta = data.get('meta') or {}
            if oldest_in_page < start_date or not meta.get('startAfter') or not meta.get('startAfterId'):
                break

            params['startAfter'] = meta['startAfter']
            params['startAfterId'] = meta['startAfterId']

        return opportunities

    async def _fetch_conversations(self, client: GHLClient, location_id: str) -> list[dict]:
        data = await client.get('/conversations/search', params={'locationId': location_id, 'limit': 100})
        return data.get('conversations', [])

    def _parse_date(self, value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)

    def _parse_timestamp_ms(self, value: int | None) -> datetime | None:
        if not value:
            return None
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
