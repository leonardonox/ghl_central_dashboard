import hmac
import time
from hashlib import sha256

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix='/auth', tags=['auth'])
SESSION_MAX_AGE = 60 * 60 * 12


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


def _verify_token(token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=401, detail='Login necessario')

    parts = token.split(':')
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail='Sessao invalida')

    username, timestamp_text, signature = parts
    payload = f'{username}:{timestamp_text}'
    if not hmac.compare_digest(signature, _signature(payload)):
        raise HTTPException(status_code=401, detail='Sessao invalida')

    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail='Sessao invalida') from exc

    if int(time.time()) - timestamp > SESSION_MAX_AGE:
        raise HTTPException(status_code=401, detail='Sessao expirada')

    settings = get_settings()
    if username != settings.dashboard_username:
        raise HTTPException(status_code=401, detail='Sessao invalida')

    return username


def require_auth(dashboard_session: str | None = Cookie(default=None)) -> str:
    return _verify_token(dashboard_session)


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
        max_age=SESSION_MAX_AGE,
    )
    return {'status': 'ok'}


@router.get('/me')
def me(dashboard_session: str | None = Cookie(default=None)) -> dict[str, str]:
    return {'username': _verify_token(dashboard_session)}


@router.post('/logout')
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie('dashboard_session')
    return {'status': 'ok'}
