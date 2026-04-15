import os
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
test_db_dir = Path("tests_runtime")
test_db_dir.mkdir(exist_ok=True)
os.environ.setdefault("USER_DB_PATH", str(test_db_dir / f"test_users_{uuid4().hex}.db"))
os.environ.setdefault("ADMIN_PASSWORD", "Admin@123456")

from fastapi.testclient import TestClient

from app.main import app


def test_healthz_reports_fixed_model():
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["model"] == "qwen3.6-plus"


def test_login_and_auth_me():
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "admin", "password": "Admin@123456"})
        assert response.status_code == 200
        token = response.json()["access_token"]

        me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "admin"
