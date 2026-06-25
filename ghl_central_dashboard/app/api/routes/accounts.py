import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import encrypt_token
from app.models.ghl_account import GHLAccount
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate

router = APIRouter(prefix='/accounts', tags=['accounts'])


def _clean_location_id(value: str) -> str:
    value = value.strip()
    match = re.search(r'/location/([^/]+)/?', value)
    if match:
        return match.group(1).strip()
    return value


def _clean_token(value: str) -> str:
    return value.strip()


@router.post('', response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    repo = AccountRepository(db)
    return repo.create(
        name=payload.name.strip(),
        location_id=_clean_location_id(payload.location_id),
        api_token_encrypted=encrypt_token(_clean_token(payload.api_token)),
    )


@router.get('', response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return AccountRepository(db).list_active()


@router.get('/all', response_model=list[AccountOut])
def list_all_accounts(db: Session = Depends(get_db)):
    return list(db.scalars(select(GHLAccount).order_by(GHLAccount.name)))


@router.put('/{account_id}', response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    account = db.get(GHLAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail='Revista nao encontrada')

    account.name = payload.name.strip()
    account.location_id = _clean_location_id(payload.location_id)
    account.active = payload.active
    if payload.api_token:
        account.api_token_encrypted = encrypt_token(_clean_token(payload.api_token))

    db.commit()
    db.refresh(account)
    return account


@router.delete('/{account_id}', response_model=AccountOut)
def deactivate_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(GHLAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail='Revista nao encontrada')

    account.active = False
    db.commit()
    db.refresh(account)
    return account
