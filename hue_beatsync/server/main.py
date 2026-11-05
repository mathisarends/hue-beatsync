from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from hue_beatsync.server.dependencies import container
from hue_beatsync.server.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        await container.close()


app = FastAPI(
    title="beatsync server",
    description="Start and stop a Hue entertainment BeatSync stream.",
    lifespan=lifespan,
)
app.include_router(router)
setup_dishka(container, app)
