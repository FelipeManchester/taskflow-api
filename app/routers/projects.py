from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import CurrentUserDep, SessionDep
from app.models import Project
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


async def get_project_or_404(
    project_id: int, session: SessionDep, current_user: CurrentUserDep
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


ProjectDep = Annotated[Project, Depends(get_project_or_404)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, session: SessionDep, current_user: CurrentUserDep
):
    project = Project(**payload.model_dump(), owner_id=current_user.id)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    session: SessionDep,
    current_user: CurrentUserDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    result = await session.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project: ProjectDep):
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    payload: ProjectUpdate, project: ProjectDep, session: SessionDep
):
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    await session.commit()
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project: ProjectDep, session: SessionDep) -> None:
    await session.delete(project)
    await session.commit()
