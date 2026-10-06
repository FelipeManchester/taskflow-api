"""Test infrastructure: a separate database, a test client and logged-in users.

You don't need to edit this file for the lab.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.database import Base, get_session
from app.main import app

TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/taskflow_test"

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

PASSWORD = "senhaforte123"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def reset_database(anyio_backend):
    """Every test starts with empty tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client(anyio_backend):
    """HTTP client that calls the app in memory, using the test database."""
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def db_session(anyio_backend):
    """Direct database access, for checks the API can't show."""
    async with TestSessionLocal() as session:
        yield session


async def register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/auth/login", data={"username": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def alice(client):
    """Auth headers for Alice."""
    return await register_and_login(client, "alice@example.com")


@pytest.fixture
async def bob(client):
    """Auth headers for Bob."""
    return await register_and_login(client, "bob@example.com")


@pytest.fixture
async def alice_project(client, alice):
    """A project owned by Alice."""
    response = await client.post(
        "/projects", json={"name": "Projeto da Alice"}, headers=alice
    )
    assert response.status_code == 201, response.text
    return response.json()
