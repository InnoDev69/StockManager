"""Recuperación de contraseña cuando el envío de correo está desactivado (sin SMTP configurado)."""
from miscellaneous import email_sender


def test_reset_password_returns_503_when_email_disabled(client, db, monkeypatch):
    monkeypatch.setattr(email_sender, "enabled", False)
    db.add_user("reset_user", "clave-123456", "reset@test.com", role="vendedor", status=1)

    r = client.post("/api/users/reset-password", json={"email": "reset@test.com"})

    assert r.status_code == 503
    assert "error" in r.get_json()
