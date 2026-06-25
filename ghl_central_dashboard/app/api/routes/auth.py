import hmac
import time
from hashlib import sha256

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix='/auth', tags=['auth'])


class LoginPayload(BaseModel):
    username: str
    password: str


def _signature(value: str) -> str:
    settings = get_settings()
    return hmac.new(settings.secret_key.encode(), value.encode(), sha256).hexdigest()


def _make_token(username: str) -> str:
    timestamp = str(int(time.time()))
    payload = f'{username}:{timestamp}'
    return f'{payload}:{_signature(payload)}'


@router.post('/login')
def login(payload: LoginPayload, response: Response) -> dict[str, str]:
    settings = get_settings()
    if payload.username != settings.dashboard_username or payload.password != settings.dashboard_password:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    response.set_cookie(
        key='dashboard_session',
        value=_make_token(payload.username),
        httponly=True,
        samesite='lax',
        max_age=60 * 60 * 12,
    )
    return {'status': 'ok'}


@router.post('/logout')
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie('dashboard_session')
    return {'status': 'ok'}
