def test_init_db_es_idempotente(db):
    db.init_db()  # segunda vez, no debe romper
    cantidad_root = db.get_count("SELECT COUNT(*) FROM users WHERE role = 'root'")
    assert cantidad_root == 1