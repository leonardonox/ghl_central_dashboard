from app.core.database import Base, engine, ensure_runtime_schema
from app.models import Conversation, DailySnapshot, GHLAccount, Lead, Opportunity  # noqa: F401

Base.metadata.create_all(bind=engine)
ensure_runtime_schema()
print('Tabelas criadas com sucesso.')
