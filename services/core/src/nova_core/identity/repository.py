from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.identity.models import AuthSession, User


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_users(self) -> int:
        return (await self._session.execute(select(func.count()).select_from(User))).scalar_one()

    async def user_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return (await self._session.execute(statement)).scalar_one_or_none()

    def add_user(self, user: User) -> None:
        self._session.add(user)

    def add_session(self, auth_session: AuthSession) -> None:
        self._session.add(auth_session)

    async def session_with_user(self, token_hash: str) -> tuple[AuthSession, User] | None:
        statement = (
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == token_hash)
        )
        row = (await self._session.execute(statement)).one_or_none()
        return (row[0], row[1]) if row is not None else None

    async def session_by_id(self, session_id: str) -> AuthSession | None:
        return await self._session.get(AuthSession, session_id)

    async def delete_session(self, auth_session: AuthSession) -> None:
        await self._session.delete(auth_session)
