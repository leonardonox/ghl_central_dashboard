import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.auth import require_auth
from app.core.config import get_settings

router = APIRouter(prefix='/deploy', tags=['deploy'], dependencies=[Depends(require_auth)])


@router.post('/render')
async def deploy_render() -> dict[str, str]:
    settings = get_settings()
    if not settings.render_deploy_hook_url:
        raise HTTPException(
            status_code=400,
            detail='RENDER_DEPLOY_HOOK_URL nao configurada no Render.',
        )

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(settings.render_deploy_hook_url)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f'Render recusou o deploy hook: {response.status_code} {response.text}',
        )

    return {'status': 'ok', 'message': 'Redeploy solicitado no Render.'}
