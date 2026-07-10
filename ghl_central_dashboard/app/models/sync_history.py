from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SyncHistory(Base):
    __tablename__ = 'sync_history'
    __table_args__ = (UniqueConstraint('account_id', 'sync_type', name='uq_sync_history_account_type'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('ghl_accounts.id'), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False, default='historical')
    days_back: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    account = relationship('GHLAccount')
