from fastapi import APIRouter, Depends, Request, Response

from nova_core.identity.deps import CurrentSession, IdentityDep, current_session
from nova_core.identity.schemas import Credentials, SessionOut, SetupOut, UserOut
from nova_core.kernel.config import Settings
from nova_core.kernel.errors import NovaError
from nova_core.kernel.ratelimit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/setup", status_code=201, dependencies=[Depends(rate_limit("auth.setup"))])
async def setup(body: Credentials, identity: IdentityDep) -> SetupOut:
    user = await identity.setup(body.username, body.password)
    return SetupOut(user=UserOut(id=user.id, username=user.username))


@router.post("/login", dependencies=[Depends(rate_limit("auth.login"))])
async def login(
    body: Credentials, request: Request, response: Response, identity: IdentityDep
) -> SessionOut:
    user, grant = await identity.login(body.username, body.password)
    settings: Settings = request.app.state.settings
    response.set_cookie(
        key=settings.session_cookie_name,
        value=grant.token,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
        httponly=True,
        samesite="strict",
        secure=settings.env == "hosted",
    )
    return SessionOut(
        user=UserOut(id=user.id, username=user.username),
        csrf_token=grant.csrf_token,
        expires_at=grant.expires_at,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, context: CurrentSession, identity: IdentityDep
) -> None:
    await identity.logout(context.session_id)
    response.delete_cookie(key=request.app.state.settings.session_cookie_name, path="/")


@router.get("/session")
async def session(request: Request, identity: IdentityDep) -> SessionOut:
    context = await current_session(request, identity)
    if context is None:
        # Tells the Studio whether to show the account creation screen or the login screen.
        raise NovaError(
            "not_authenticated",
            401,
            "Authentication is required.",
            extra={"setup_required": not await identity.is_setup()},
        )
    return SessionOut(
        user=UserOut(id=context.user_id, username=context.username),
        csrf_token=context.csrf_token,
        expires_at=context.expires_at,
    )
