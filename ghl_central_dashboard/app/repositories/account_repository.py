from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ghl_account import GHLAccount


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, location_id: str, api_token_encrypted: str) -> GHLAccount:
        account = GHLAccount(name=name, location_id=location_id, api_token_encrypted=api_token_encrypted)
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def list_active(self) -> list[GHLAccount]:
        return list(self.db.scalars(select(GHLAccount).where(GHLAccount.active.is_(True))))
