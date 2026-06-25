from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Opportunity(Base):
    __tablename__ = 'opportunities'
    __table_args__ = (UniqueConstraint('ghl_opportunity_id', 'account_id', name='uq_opportunity_account'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ghl_opportunity_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('ghl_accounts.id'), nullable=False, index=True)
    contact_id: Mapped[str | None] = mapped_column(String(150), index=True)
    pipeline_id: Mapped[str | None] = mapped_column(String(150))
    pipeline_stage_id: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str | None] = mapped_column(String(50), index=True)
    monetary_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    source: Mapped[str | None] = mapped_column(String(150), index=True)
    ghl_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    account = relationship('GHLAccount', back_populates='opportunities')
