import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text


def build_db_url(db_path: Path) -> str:
    return f"sqlite+pysqlite:///{db_path.as_posix()}"


def prepare_env(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url


def run_migrations(base_dir: Path, db_url: str) -> None:
    alembic_cfg = Config(str(base_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test.db"
    db_url = build_db_url(db_path)
    prepare_env(db_url)

    run_migrations(base_dir, db_url)

    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.main import app
    from app.models.user import User

    with SessionLocal() as db:
        version = db.execute(text("select version_num from alembic_version")).scalar_one()
        assert version

    with SessionLocal() as db:
        user = User(tg_user_id=1001, roles=["advertiser"])
        user2 = User(tg_user_id=2002, roles=["advertiser"])
        db.add_all([user, user2])
        db.commit()
        db.refresh(user)
        db.refresh(user2)

    token = create_access_token(user.id)
    token2 = create_access_token(user2.id)
    client = TestClient(app)

    def headers_for(token_value: str) -> dict:
        return {"Authorization": f"Bearer {token_value}"}

    def expect(code: int, response) -> None:
        assert response.status_code == code, response.text

    headers = headers_for(token)
    headers2 = headers_for(token2)

    response = client.post("/channels/", json={}, headers=headers)
    expect(422, response)

    response = client.post(
        "/channels/",
        json={"tg_chat_id": 123456, "username": "test", "title": "Test"},
        headers=headers,
    )
    expect(200, response)
    channel_id = response.json()["id"]

    response = client.post(
        "/channels/",
        json={"tg_chat_id": 123456, "username": "dup", "title": "Dup"},
        headers=headers,
    )
    expect(409, response)

    response = client.get("/channels/", headers=headers)
    expect(200, response)
    assert len(response.json()) == 1

    response = client.get(f"/channels/{channel_id}", headers=headers)
    expect(200, response)

    response = client.get("/channels/999999", headers=headers)
    expect(404, response)

    response = client.patch(
        f"/channels/{channel_id}",
        json={"title": "Updated"},
        headers=headers,
    )
    expect(200, response)
    assert response.json()["title"] == "Updated"

    response = client.post("/listings/", json={}, headers=headers)
    expect(422, response)

    response = client.post(
        "/listings/",
        json={"channel_id": channel_id, "price_usd": 10.5, "active": True},
        headers=headers,
    )
    expect(200, response)
    listing_id = response.json()["id"]

    response = client.post(
        "/listings/",
        json={"channel_id": 999999, "price_usd": 10.5},
        headers=headers,
    )
    expect(404, response)

    response = client.get(f"/listings/{listing_id}")
    expect(200, response)

    response = client.patch(
        f"/listings/{listing_id}",
        json={"price_usd": 12.0},
        headers=headers,
    )
    expect(200, response)
    assert response.json()["price_usd"] == 12.0

    response = client.get("/listings/?active=true&price_min=10&price_max=20")
    expect(200, response)
    assert any(item["id"] == listing_id for item in response.json())

    response = client.post(
        "/requests/",
        json={"budget": 100.0, "niche": "tech", "languages": ["en"]},
        headers=headers,
    )
    expect(200, response)
    request_id = response.json()["id"]

    response = client.get(f"/requests/{request_id}")
    expect(200, response)

    response = client.patch(
        f"/requests/{request_id}",
        json={"budget": 150.0},
        headers=headers,
    )
    expect(200, response)
    assert response.json()["budget"] == 150.0

    response = client.patch(
        f"/requests/{request_id}",
        json={"budget": 200.0},
        headers=headers2,
    )
    expect(403, response)

    response = client.get("/requests/?budget_min=50&budget_max=200")
    expect(200, response)
    assert any(item["id"] == request_id for item in response.json())

    print("OK")


if __name__ == "__main__":
    main()
