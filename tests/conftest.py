from typing import Callable

import httpx
import pytest

from main import app


@pytest.fixture(scope="function")
async def client_factory() -> Callable:
    """A factory to construct an HTTPX AsyncClient."""
    clients = []

    def create_client() -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        client_ = httpx.AsyncClient(transport=transport, base_url="http://test")
        clients.append(client_)
        return client_

    yield create_client

    for client_ in clients:
        await client_.aclose()


@pytest.fixture()
def client(client_factory) -> httpx.AsyncClient:
    """An HTTP session."""
    return client_factory()
