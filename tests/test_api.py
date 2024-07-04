async def test_get_root(client):
    """Verify we can load the openapi.json spec."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data == {"message": "Hello World"}
