from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException

from server.configuration import DefaultsStore
from server.schemas import StatusResponse, SyncSettings
from server.sync import SyncAlreadyRunning, SyncManager, SyncNotRunning

router = APIRouter(route_class=DishkaRoute)


@router.get("/status", response_model=StatusResponse, operation_id="get_status")
async def status(manager: FromDishka[SyncManager]) -> StatusResponse:
    return StatusResponse(running=manager.running, area=manager.area)


@router.post("/start", response_model=StatusResponse, operation_id="start_sync")
async def start(
    request: SyncSettings,
    manager: FromDishka[SyncManager],
    defaults: FromDishka[DefaultsStore],
) -> StatusResponse:
    resolved = defaults.resolve(request)
    if not resolved.area:
        raise HTTPException(
            status_code=422,
            detail=(
                "area is required (pass it, or configure a default via PUT /defaults)"
            ),
        )
    try:
        await manager.start(
            resolved.area,
            mode=resolved.visual,
            device=resolved.device,
            rate=resolved.rate,
            sensitivity=resolved.sensitivity,
            gamma=resolved.gamma,
            floor=resolved.floor,
            max_frequency=resolved.max_frequency,
            exclusive=resolved.exclusive,
            gain=resolved.gain,
        )
    except (SyncAlreadyRunning, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StatusResponse(running=manager.running, area=manager.area)


@router.post("/stop", response_model=StatusResponse, operation_id="stop_sync")
async def stop(manager: FromDishka[SyncManager]) -> StatusResponse:
    try:
        await manager.stop()
    except SyncNotRunning as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StatusResponse(running=manager.running, area=manager.area)


@router.get("/defaults", response_model=SyncSettings, operation_id="get_defaults")
async def get_defaults(defaults: FromDishka[DefaultsStore]) -> SyncSettings:
    return defaults.current


@router.put("/defaults", response_model=SyncSettings, operation_id="set_defaults")
async def set_defaults(
    request: SyncSettings, defaults: FromDishka[DefaultsStore]
) -> SyncSettings:
    return defaults.update(request)
