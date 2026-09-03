from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.manager import SyncManager

manager = SyncManager()


def get_manager() -> SyncManager:
    return manager


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        if manager.running:
            await manager.stop()
