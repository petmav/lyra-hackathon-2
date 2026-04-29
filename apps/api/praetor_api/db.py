from collections.abc import AsyncIterator
import os

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from praetor_api.settings import get_settings

settings = get_settings()
engine_kwargs = {"pool_pre_ping": True}
if os.getenv("PRAETOR_RUN_DB_TESTS") == "1":
    engine_kwargs["poolclass"] = NullPool

async_engine = create_async_engine(
    settings.pg_dsn,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
