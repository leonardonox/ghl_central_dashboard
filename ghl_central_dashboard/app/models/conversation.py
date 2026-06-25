from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    __tablename__ = 'conversations'
    __table_args__ = (UniqueConstraint('ghl_conversation_id', 'account_id', name='uq_conversation_account'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ghl_conversation_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('ghl_accounts.id'), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(String(150), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(50))
    last_message_type: Mapped[str | None] = mapped_column(String(80), index=True)
    last_message_direction: Mapped[str | None] = mapped_column(String(80), index=True)
    last_message_date: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    last_inbound_whatsapp_message_date: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    account = relationship('GHLAccount')
