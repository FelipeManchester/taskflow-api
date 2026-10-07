from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import ProjectDep, SessionDep
from app.models import Task, User
from app.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


async def ensure_assignee_exists(
    session: AsyncSession, assignee_id: int | None
) -> None:
    if assignee_id is None:
        return
    user = await session.get(User, assignee_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Assignee not found",
        )


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    project: ProjectDep,
    session: SessionDep,
):
    await ensure_assignee_exists(session, payload.assignee_id)
    task = Task(**payload.model_dump(), project_id=project.id)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(session: SessionDep, project: ProjectDep):
    result = await session.execute(
        select(Task).where(Task.project_id == project.id).order_by(Task.id)
    )
    return result.scalars().all()


async def get_task_or_404(
    task_id: int, session: SessionDep, project: ProjectDep
) -> Task:
    task = await session.get(Task, task_id)
    if task is None or task.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return task


TaskDep = Annotated[Task, Depends(get_task_or_404)]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task: TaskDep):
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(payload: TaskUpdate, task: TaskDep, session: SessionDep):
    updates = payload.model_dump(exclude_unset=True)
    if "assignee_id" in updates:
        await ensure_assignee_exists(session, updates["assignee_id"])
    for field, value in updates.items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task: TaskDep, session: SessionDep) -> None:
    await session.delete(task)
    await session.commit()
