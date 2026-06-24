from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx
from fastapi import HTTPException, Request

from marble_api._config import config


def _if_auth_enabled(func: Callable) -> Callable:
    """Only run function if magpie authentication is enabled."""

    @wraps(func)
    async def _(*args, **kwargs) -> Any:  # noqa: ANN401
        if config.magpie_auth_enabled:
            return await func(*args, **kwargs)

    return _


async def _get_authenticated_magpie_user_session(cookies: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(cookies=cookies) as client:
        try:
            response = await client.get(f"{config.magpie_url}/session")
        except httpx.HTTPError:
            raise HTTPException(status_code=403, detail="Forbidden: unable to authenticate")
        json = response.json()
        if response.status_code == 200 and json["authenticated"]:
            return json
        raise HTTPException(status_code=403, detail="Forbidden")


@_if_auth_enabled
async def authenticate_magpie_user(request: Request, user: str) -> None:
    """Raise exception if the user's username does not match the request path."""
    magpie_session = await _get_authenticated_magpie_user_session(request.cookies)
    if magpie_session.get("user", {}).get("user_name") != user:
        raise HTTPException(status_code=403, detail="Forbidden")


@_if_auth_enabled
async def authenticate_magpie_admin(request: Request) -> None:
    """Raise exception if the user is not part of the admin group."""
    magpie_session = await _get_authenticated_magpie_user_session(request.cookies)
    if config.magpie_admin_group not in magpie_session.get("user", {}).get("group_names", []):
        raise HTTPException(status_code=403, detail="Forbidden")
