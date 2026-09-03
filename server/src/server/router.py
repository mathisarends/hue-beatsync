from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server.lifespan import get_manager
from server.manager import SyncAlreadyRunning, SyncManager, SyncNotRunning
from server.schemas import StartRequest, StatusResponse

router = APIRouter()

ManagerDep = Annotated[SyncManager, Depends(get_manager)]


@router.get("/status", response_model=StatusResponse)
async def status(manager: ManagerDep) -> StatusResponse:
    return StatusResponse(running=manager.running, area=manager.area)


@router.post("/start", response_model=StatusResponse)
async def start(request: StartRequest, manager: ManagerDep) -> StatusResponse:
    settings = request.model_dump(exclude={"area", "visual"})
    try:
        await manager.start(request.area, mode=request.visual, **settings)
    except (SyncAlreadyRunning, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StatusResponse(running=manager.running, area=manager.area)


@router.post("/stop", response_model=StatusResponse)
async def stop(manager: ManagerDep) -> StatusResponse:
    try:
        await manager.stop()
    except SyncNotRunning as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StatusResponse(running=manager.running, area=manager.area)
