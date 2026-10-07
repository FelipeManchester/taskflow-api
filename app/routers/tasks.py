from fastapi import APIRouter

from app.dependencies import CurrentUserDep
from app.schemas import TaskRead

router = APIRouter(prefix="/projects/{project}/tasks", tags=["tasks"])


@router.post("/projects/{project}/tasks", response_model=TaskRead)
async def read_me(current_user: CurrentUserDep):
    return current_user
