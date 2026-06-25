from app.core.database import Base, engine
from app.models import Conversation, DailySnapshot, GHLAccount, Lead, Opportunity  # noqa: F401

Base.metadata.create_all(bind=engine)
print('Tabelas criadas com sucesso.')
