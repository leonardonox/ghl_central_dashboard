from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DailySnapshot(Base):
    __tablename__ = 'daily_snapshots'
    __table_args__ = (UniqueConstraint('snapshot_date', 'account_id', name='uq_daily_snapshot_account_date'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('ghl_accounts.id'), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    new_leads: Mapped[int] = mapped_column(Integer, default=0)
    new_leads_with_channel: Mapped[int] = mapped_column(Integer, default=0)
    attendances: Mapped[int] = mapped_column(Integer, default=0)
    sales: Mapped[int] = mapped_column(Integer, default=0)
    hsm_leads: Mapped[int] = mapped_column(Integer, default=0)
    whatsapp_contacts: Mapped[int] = mapped_column(Integer, default=0)
    inbox_conversations: Mapped[int] = mapped_column(Integer, default=0)
    lead_channels: Mapped[list[dict] | None] = mapped_column(JSON)
    metric_version: Mapped[int] = mapped_column(Integer, default=4)
    attendance_rate: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    sales_rate: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    channel_identified_rate: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    account = relationship('GHLAccount')
