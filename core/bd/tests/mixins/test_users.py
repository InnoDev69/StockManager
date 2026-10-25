import pytest


def test_root_existe_por_defecto(db):
    assert db.user_exists("root", "otro@mail.com") is True
    assert db.user_exists("otro_user", "root@root.com") is True
    assert db.user_exists("inexistente", "no@existe.com") is False


def test_add_user_y_consultas(db):
    db.add_user("vendedor1", "hash_secreto", "v1@tienda.com", role="vendedor", status=1)

    user = db.get_user_by_email("v1@tienda.com")
    assert user is not None
    user_id, username, password_hash, role = user
    assert username == "vendedor1"
    assert password_hash == "hash_secreto"
    assert role == "vendedor"

    assert db.get_username_by_id(user_id) == "vendedor1"


def test_add_user_duplicado_no_inserta_otra_fila(db):
    db.add_user("juan", "hash1", "juan@mail.com")
    # Mismo username o mismo email: add_user hace return silencioso
    db.add_user("juan", "hash2", "otro@mail.com")
    db.add_user("juan_nuevo", "hash3", "juan@mail.com")

    assert db.get_count("SELECT COUNT(*) FROM users WHERE username LIKE 'juan%'") == 1


def test_consultas_usuario_inexistente(db):
    assert db.get_user_by_email("fantasma@mail.com") is None
    assert db.get_username_by_id(9999) is None