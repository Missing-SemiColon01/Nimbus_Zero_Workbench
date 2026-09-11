from fastapi import APIRouter, HTTPException, Request

from backend.models.router import NoCompatibleModelError
from backend.schemas.tasks import TaskCreate, TaskResponse

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    return {"status": "ok", "sovereign_mode": request.app.state.settings.sovereign_mode}


@router.get("/models")
async def models(request: Request):
    return [{"id": item.id, "capabilities": sorted(item.capabilities), "modalities": sorted(item.modalities)} for item in request.app.state.registry.models]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(payload: TaskCreate, request: Request):
    try:
        state = request.app.state.runtime.begin(payload.request, payload.capabilities, payload.modality)
    except NoCompatibleModelError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return TaskResponse(task_id=state.task_id, status=state.status, selected_model=state.selected_model, plan=state.plan)
