import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import Base, get_db
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.auth.password import hash_password

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create non-admin user
    normal_user = User(
        username="normaluser",
        email="user@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
        is_admin=False
    )
    # Create admin user
    admin_user = User(
        username="adminuser",
        email="admin@example.com",
        password_hash=hash_password("adminpassword123"),
        is_active=True,
        is_admin=True
    )
    db.add(normal_user)
    db.add(admin_user)
    db.commit()
    db.refresh(normal_user)
    db.refresh(admin_user)

    # Create dummy contract
    contract = Contract(
        user_id=normal_user.id,
        original_filename="sample_contract.pdf",
        stored_filename="sample_stored_123.pdf",
        file_path="/tmp/sample_stored_123.pdf",
        file_size=1024,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED
    )
    db.add(contract)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)


def test_admin_login_success():
    response = client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@example.com"
    assert data["user"]["is_admin"] is True


def test_admin_login_fail_non_admin():
    response = client.post(
        "/admin/auth/login",
        json={"email": "user@example.com", "password": "password123"}
    )
    assert response.status_code == 403
    assert "Admin privileges required" in response.json()["detail"]


def test_admin_user_management():
    # Login as admin to get token
    login_resp = client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword123"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get users list
    resp = client.get("/admin/users", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["users"]) == 2

    normal_user_id = [u for u in data["users"] if u["email"] == "user@example.com"][0]["id"]

    # Toggle user active status
    status_resp = client.patch(
        f"/admin/users/{normal_user_id}/status",
        headers=headers,
        json={"is_active": False}
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["is_active"] is False

    # Promote user to admin
    role_resp = client.patch(
        f"/admin/users/{normal_user_id}/role",
        headers=headers,
        json={"is_admin": True}
    )
    assert role_resp.status_code == 200
    assert role_resp.json()["is_admin"] is True


def test_admin_contract_management():
    login_resp = client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword123"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get contracts list
    resp = client.get("/admin/contracts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    contract_id = data["contracts"][0]["id"]

    # Update contract status
    update_resp = client.patch(
        f"/admin/contracts/{contract_id}/status",
        headers=headers,
        json={"status": "COMPLETED"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "COMPLETED"

    # Delete contract
    del_resp = client.delete(f"/admin/contracts/{contract_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Contract deleted successfully"


def test_admin_dashboard_stats():
    login_resp = client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword123"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/admin/dashboard/stats", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_users"] == 2
    assert stats["admin_users"] == 1
    assert stats["total_contracts"] == 1
