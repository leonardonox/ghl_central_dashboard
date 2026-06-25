from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Lead(Base):
    __tablename__ = 'leads'
    __table_args__ = (UniqueConstraint('ghl_contact_id', 'account_id', name='uq_lead_contact_account'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ghl_contact_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('ghl_accounts.id'), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(150), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(150), index=True)
    ghl_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    account = relationship('GHLAccount', back_populates='leads')
