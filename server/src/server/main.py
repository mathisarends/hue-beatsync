from fastapi import FastAPI

from server.lifespan import lifespan
from server.router import router

app = FastAPI(
    title="hue-beatsync server",
    description="Start and stop a Hue entertainment BeatSync stream.",
    lifespan=lifespan,
)
app.include_router(router)
