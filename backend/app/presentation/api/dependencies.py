from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from ...application.errors import AuthenticationRequired, AuthenticationServiceUnavailable
from ...container import AppContainer
from ...domain.identity import AuthenticatedIdentity


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


ContainerDependency = Annotated[AppContainer, Depends(get_container)]


@dataclass(frozen=True, slots=True)
class RequestAuthentication:
    token: str
    identity: AuthenticatedIdentity


async def required_authentication(request: Request, container: AppContainer) -> RequestAuthentication:
    token = request.cookies.get(container.settings.session_cookie_name, "")
    if not token:
        raise AuthenticationRequired
    if container.get_current_session is None:
        raise AuthenticationServiceUnavailable
    identity = await container.get_current_session.execute(token)
    return RequestAuthentication(token, identity)


async def optional_authentication(request: Request, container: AppContainer) -> RequestAuthentication | None:
    token = request.cookies.get(container.settings.session_cookie_name, "")
    if not token:
        return None
    if container.get_current_session is None:
        raise AuthenticationServiceUnavailable
    try:
        identity = await container.get_current_session.execute(token)
    except AuthenticationRequired:
        return None
    return RequestAuthentication(token, identity)
