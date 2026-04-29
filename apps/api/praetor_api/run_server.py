from __future__ import annotations

import os

import uvicorn
from alembic import command
from alembic.config import Config

from praetor_api.settings import get_settings


def maybe_migrate() -> None:
    settings = get_settings()
    if settings.data_mode != "production" or not settings.auto_migrate:
        return
    command.upgrade(Config("alembic.ini"), "head")


def main() -> None:
    maybe_migrate()
    uvicorn.run(
        "praetor_api.main:app",
        host=os.getenv("PRAETOR_API_HOST", "0.0.0.0"),
        port=int(os.getenv("PRAETOR_API_PORT", "8000")),
        reload=os.getenv("PRAETOR_API_RELOAD") == "1",
    )


if __name__ == "__main__":
    main()
