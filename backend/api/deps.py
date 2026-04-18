from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import session


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session() as s:
        yield s


def current_user() -> str:
    return "maya_chen"


SessionDep = Depends(get_session)
UserDep = Depends(current_user)
