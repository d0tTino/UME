from typing import Any, cast

from fastapi.testclient import TestClient

from ume.api import app
from ume.recommendation_feedback import feedback_store
from ume.config import settings


def _token(client: TestClient) -> str:
    data: Any = client.post(
        "/token",
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


def test_feedback_accept_reject() -> None:
    client = TestClient(app)
    token = _token(client)
    res = client.post(
        "/feedback/accept",
        json={"id": "rec1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.post(
        "/feedback/reject",
        json={"id": "rec2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    entries = {(i, s) for i, s, _ in feedback_store.list_feedback()}
    assert ("rec1", "accepted") in entries
    assert ("rec2", "rejected") in entries
