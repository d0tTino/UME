from typing import Any, cast

from fastapi.testclient import TestClient

from ume.api import app
from ume.config import settings


def _token(client: TestClient) -> str:
    data: Any = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    ).json()
    return cast(str, data["access_token"])


def test_get_recommendations() -> None:
    client = TestClient(app)
    token = _token(client)
    res = client.get("/recommendations", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert data and "id" in data[0]


def test_feedback() -> None:
    client = TestClient(app)
    token = _token(client)
    res = client.post(
        "/recommendations/feedback",
        json={"id": "rec1", "feedback": "accepted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
