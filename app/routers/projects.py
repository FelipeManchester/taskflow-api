from datetime import UTC, datetime
from itertools import count

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

_projects: dict[int, ProjectRead] = {}
_ids = count(start=1)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate) -> ProjectRead:
    project = ProjectRead(
        id=next(_ids),
        created_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    _projects[project.id] = project
    return project


@router.get("/")
def list_projects(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[ProjectRead]:
    projects = list(_projects.values())
    return projects[skip : skip + limit]


@router.get("/{project_id}")
def get_project(project_id: int) -> ProjectRead:
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.patch("/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate) -> ProjectRead:
    project = get_project(project_id)
    updates = payload.model_dump(exclude_unset=True)
    updated = project.model_copy(update=updates)
    _projects[project_id] = updated
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int) -> None:
    get_project(project_id)
    del _projects[project_id]
