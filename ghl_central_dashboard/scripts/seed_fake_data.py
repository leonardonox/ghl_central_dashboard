from datetime import datetime, timedelta
from random import randint, choice

from app.core.database import SessionLocal
from app.core.security import encrypt_token
from app.models.ghl_account import GHLAccount
from app.models.lead import Lead

accounts = ['Veredas', 'DCS', 'Cajuína']
sources = ['Google', 'Instagram/Facebook', 'Indicação', 'Convite', 'Já publiquei', 'LinkedIn']

db = SessionLocal()
try:
    created_accounts = []
    for name in accounts:
        account = GHLAccount(name=name, location_id=f'test-{name.lower()}', api_token_encrypted=encrypt_token('fake-token-123456789'))
        db.add(account)
        db.flush()
        created_accounts.append(account)

    for account in created_accounts:
        for days_back in range(0, 10):
            for i in range(randint(5, 30)):
                created_at = datetime.utcnow() - timedelta(days=days_back, minutes=randint(0, 1000))
                db.add(Lead(
                    ghl_contact_id=f'{account.location_id}-{days_back}-{i}',
                    account_id=account.id,
                    name='Lead Teste',
                    email=f'lead{i}@teste.com',
                    phone='000000000',
                    source=choice(sources),
                    ghl_created_at=created_at,
                    raw_data={'fake': True},
                ))
    db.commit()
    print('Dados fake criados.')
finally:
    db.close()
