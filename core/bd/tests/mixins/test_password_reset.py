def test_flujo_completo_password_reset(db):
    email = "root@root.com"
    assert db.get_reset_code(email) == (None, None)
    assert db.verify_code(email, "123456") is False

    # Guardar y verificar código recién creado (< 15 min)
    db.save_reset_code(email, "123456")
    code, created_at = db.get_reset_code(email)
    assert code == "123456"
    assert created_at is not None
    assert db.verify_code(email, "123456") is True
    assert db.verify_code(email, "000000") is False

    # Actualizar contraseña y limpiar código
    db.update_user_password(email, "nuevo_hash_seguro")
    assert db.get_user_by_email(email)[2] == "nuevo_hash_seguro"

    db.delete_reset_code(email)
    assert db.get_reset_code(email) == (None, None)
    assert db.verify_code(email, "123456") is False


def test_verify_code_expirado_devuelve_false(db):
    email = "root@root.com"
    db.execute_query(
        "INSERT INTO password_resets (email, code, created_at) VALUES (?, ?, datetime('now', '-20 minutes'))",
        (email, "999999"),
        fetch=False,
    )
    assert db.verify_code(email, "999999") is False