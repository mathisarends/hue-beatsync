from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from server.dependencies import container
from server.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        await container.close()


app = FastAPI(
    title="hue-beatsync server",
    description="Start and stop a Hue entertainment BeatSync stream.",
    lifespan=lifespan,
)
app.include_router(router)
setup_dishka(container, app)
