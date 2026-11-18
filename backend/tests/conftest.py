import pytest
from typing import AsyncGenerator
import httpx
from httpx import ASGITransport

from app.main import app
from app.core.database import init_db


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database tables are initialized before running test suite."""
    await init_db()


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client fixture for testing endpoints."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
