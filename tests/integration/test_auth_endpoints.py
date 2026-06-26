import pytest


class TestAuthEndpoints:
    def test_login_success(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "AdminPass1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    def test_login_wrong_password(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "WrongPass1",
        })
        assert resp.status_code == 401
        # Mensagem generica — nao especifica se email ou senha
        assert "invalidas" in resp.json()["message"].lower() or "invalido" in resp.json()["message"].lower()

    def test_login_nonexistent_email(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "naoexiste@test.com",
            "password": "AnyPass1",
        })
        assert resp.status_code == 401

    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "admin@test.com"

    def test_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 403  # HTTPBearer retorna 403 sem credentials

    def test_password_not_in_response(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "AdminPass1",
        })
        assert "password" not in str(resp.json())
        assert "hash" not in str(resp.json())

    def test_refresh_token(self, client, admin_user):
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "AdminPass1",
        })
        refresh_token = login_resp.json()["refresh_token"]
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_logout_invalidates_refresh_token(self, client, admin_user):
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "AdminPass1",
        })
        refresh_token = login_resp.json()["refresh_token"]
        client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        # Apos logout, refresh deve falhar
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
