from fastapi import APIRouter

from app.dependencies import CurrentUserDep
from app.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(current_user: CurrentUserDep):
    return current_user
