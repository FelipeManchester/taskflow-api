"""Lab: Task CRUD nested under /projects/{project_id}/tasks.

These tests are the spec. Don't edit them: make them pass.
"""

from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.models import Task

pytestmark = pytest.mark.anyio


def tasks_url(project_id: int) -> str:
    return f"/projects/{project_id}/tasks"


def task_url(project_id: int, task_id: int) -> str:
    return f"/projects/{project_id}/tasks/{task_id}"


async def create_task(client, headers, project_id, **fields):
    payload = {"title": "Task de teste", **fields}
    response = await client.post(tasks_url(project_id), json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def create_project(client, headers, name="Outro projeto"):
    response = await client.post("/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# US1: create a task
# ---------------------------------------------------------------------------


async def test_create_task_returns_201_with_defaults(client, alice, alice_project):
    response = await client.post(
        tasks_url(alice_project["id"]), json={"title": "Escrever testes"}, headers=alice
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Escrever testes"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["description"] is None
    assert body["due_date"] is None
    assert body["assignee_id"] is None
    assert body["project_id"] == alice_project["id"]
    assert isinstance(body["id"], int)
    assert body["created_at"]
    assert body["updated_at"]


async def test_create_task_with_all_fields(client, alice, alice_project):
    payload = {
        "title": "Deploy",
        "description": "Subir para produção",
        "status": "in_progress",
        "priority": "high",
        "due_date": "2026-12-31",
    }

    response = await client.post(
        tasks_url(alice_project["id"]), json=payload, headers=alice
    )

    assert response.status_code == 201
    body = response.json()
    for field, value in payload.items():
        assert body[field] == value


async def test_create_task_ignores_project_id_in_body(client, alice, alice_project):
    response = await client.post(
        tasks_url(alice_project["id"]),
        json={"title": "X", "project_id": 999999},
        headers=alice,
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == alice_project["id"]


# ---------------------------------------------------------------------------
# US2: authentication and project ownership
# ---------------------------------------------------------------------------


async def test_task_routes_require_authentication(client, alice_project):
    url = tasks_url(alice_project["id"])

    assert (await client.get(url)).status_code == 401
    assert (await client.post(url, json={"title": "X"})).status_code == 401


async def test_cannot_create_task_in_another_users_project(client, bob, alice_project):
    response = await client.post(
        tasks_url(alice_project["id"]), json={"title": "Invasão"}, headers=bob
    )

    assert response.status_code == 404


async def test_create_task_in_nonexistent_project_returns_404(client, alice):
    response = await client.post(tasks_url(999999), json={"title": "X"}, headers=alice)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# US3: validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "x" * 201},
        {"title": "X", "status": "banana"},
        {"title": "X", "priority": "urgent"},
        {"title": "X", "due_date": "not-a-date"},
        {"title": "X", "description": "x" * 5001},
    ],
)
async def test_create_task_rejects_invalid_payload(
    client, alice, alice_project, payload
):
    response = await client.post(
        tasks_url(alice_project["id"]), json=payload, headers=alice
    )

    assert response.status_code == 422


async def test_description_accepts_up_to_5000_chars(client, alice, alice_project):
    response = await client.post(
        tasks_url(alice_project["id"]),
        json={"title": "X", "description": "x" * 5000},
        headers=alice,
    )

    assert response.status_code == 201


async def test_create_task_with_existing_assignee(client, alice, alice_project):
    alice_id = (await client.get("/users/me", headers=alice)).json()["id"]

    response = await client.post(
        tasks_url(alice_project["id"]),
        json={"title": "X", "assignee_id": alice_id},
        headers=alice,
    )

    assert response.status_code == 201
    assert response.json()["assignee_id"] == alice_id


async def test_create_task_with_nonexistent_assignee_returns_422(
    client, alice, alice_project
):
    response = await client.post(
        tasks_url(alice_project["id"]),
        json={"title": "X", "assignee_id": 999999},
        headers=alice,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Assignee not found"


# ---------------------------------------------------------------------------
# US4: list tasks of a project
# ---------------------------------------------------------------------------


async def test_list_returns_only_tasks_of_the_project_ordered_by_id(
    client, alice, alice_project
):
    other_project = await create_project(client, alice)
    first = await create_task(client, alice, alice_project["id"], title="Primeira")
    second = await create_task(client, alice, alice_project["id"], title="Segunda")
    await create_task(client, alice, other_project["id"], title="De outro projeto")

    response = await client.get(tasks_url(alice_project["id"]), headers=alice)

    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == [first["id"], second["id"]]


async def test_list_of_empty_project_returns_empty_list(client, alice, alice_project):
    response = await client.get(tasks_url(alice_project["id"]), headers=alice)

    assert response.status_code == 200
    assert response.json() == []


async def test_cannot_list_tasks_of_another_users_project(client, bob, alice_project):
    response = await client.get(tasks_url(alice_project["id"]), headers=bob)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# US5: get one task
# ---------------------------------------------------------------------------


async def test_get_task_returns_200(client, alice, alice_project):
    task = await create_task(client, alice, alice_project["id"], title="Buscar")

    response = await client.get(
        task_url(alice_project["id"], task["id"]), headers=alice
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Buscar"


async def test_get_nonexistent_task_returns_404(client, alice, alice_project):
    response = await client.get(task_url(alice_project["id"], 999999), headers=alice)

    assert response.status_code == 404


async def test_get_task_through_wrong_project_returns_404(client, alice, alice_project):
    other_project = await create_project(client, alice)
    task = await create_task(client, alice, alice_project["id"])

    response = await client.get(
        task_url(other_project["id"], task["id"]), headers=alice
    )

    assert response.status_code == 404


async def test_cannot_get_task_of_another_users_project(
    client, alice, bob, alice_project
):
    task = await create_task(client, alice, alice_project["id"])

    response = await client.get(task_url(alice_project["id"], task["id"]), headers=bob)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# US6: update a task
# ---------------------------------------------------------------------------


async def test_patch_updates_only_sent_fields(client, alice, alice_project):
    task = await create_task(
        client, alice, alice_project["id"], title="Original", description="Desc"
    )

    response = await client.patch(
        task_url(alice_project["id"], task["id"]),
        json={"status": "done"},
        headers=alice,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["title"] == "Original"
    assert body["description"] == "Desc"


async def test_patch_can_clear_nullable_fields(client, alice, alice_project):
    task = await create_task(
        client,
        alice,
        alice_project["id"],
        description="Desc",
        due_date="2026-12-31",
    )

    response = await client.patch(
        task_url(alice_project["id"], task["id"]),
        json={"description": None, "due_date": None},
        headers=alice,
    )

    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["due_date"] is None


@pytest.mark.parametrize("field", ["title", "status", "priority"])
async def test_patch_rejects_null_on_required_fields(
    client, alice, alice_project, field
):
    task = await create_task(client, alice, alice_project["id"])

    response = await client.patch(
        task_url(alice_project["id"], task["id"]),
        json={field: None},
        headers=alice,
    )

    assert response.status_code == 422


async def test_patch_bumps_updated_at(client, alice, alice_project):
    task = await create_task(client, alice, alice_project["id"])

    response = await client.patch(
        task_url(alice_project["id"], task["id"]),
        json={"title": "Novo título"},
        headers=alice,
    )

    assert response.status_code == 200
    before = datetime.fromisoformat(task["updated_at"])
    after = datetime.fromisoformat(response.json()["updated_at"])
    assert after > before


async def test_patch_with_nonexistent_assignee_returns_422(
    client, alice, alice_project
):
    task = await create_task(client, alice, alice_project["id"])

    response = await client.patch(
        task_url(alice_project["id"], task["id"]),
        json={"assignee_id": 999999},
        headers=alice,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Assignee not found"


async def test_patch_task_through_wrong_project_returns_404(
    client, alice, alice_project
):
    other_project = await create_project(client, alice)
    task = await create_task(client, alice, alice_project["id"])

    response = await client.patch(
        task_url(other_project["id"], task["id"]),
        json={"title": "X"},
        headers=alice,
    )

    assert response.status_code == 404


async def test_cannot_patch_task_of_another_users_project(
    client, alice, bob, alice_project
):
    task = await create_task(client, alice, alice_project["id"])

    response = await client.patch(
        task_url(alice_project["id"], task["id"]),
        json={"title": "Invasão"},
        headers=bob,
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# US7: delete a task
# ---------------------------------------------------------------------------


async def test_delete_task_returns_204_and_removes_it(client, alice, alice_project):
    task = await create_task(client, alice, alice_project["id"])
    url = task_url(alice_project["id"], task["id"])

    response = await client.delete(url, headers=alice)

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(url, headers=alice)).status_code == 404


async def test_cannot_delete_task_of_another_users_project(
    client, alice, bob, alice_project
):
    task = await create_task(client, alice, alice_project["id"])
    url = task_url(alice_project["id"], task["id"])

    response = await client.delete(url, headers=bob)

    assert response.status_code == 404
    assert (await client.get(url, headers=alice)).status_code == 200


# ---------------------------------------------------------------------------
# US8: deleting a project deletes its tasks
# ---------------------------------------------------------------------------


async def test_deleting_project_deletes_its_tasks(
    client, alice, alice_project, db_session
):
    await create_task(client, alice, alice_project["id"])
    await create_task(client, alice, alice_project["id"])

    response = await client.delete(f"/projects/{alice_project['id']}", headers=alice)
    assert response.status_code == 204

    remaining = await db_session.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.project_id == alice_project["id"])
    )
    assert remaining == 0
