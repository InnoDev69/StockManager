import pytest
from core.bd.bdErrors import DatabaseError

ROOT_ID = 1


def test_ciclo_de_vida_notificaciones(db):
    assert db.get_unread_count(ROOT_ID) == 0
    assert db.get_unread_notifications(ROOT_ID) == []

    db.create_notification(ROOT_ID, "Alerta 1", "Mensaje 1", "warning", "/items")
    db.create_notification(ROOT_ID, "Info 2", "Mensaje 2", "info")

    assert db.get_unread_count(ROOT_ID) == 2

    unread = db.get_unread_notifications(ROOT_ID, limit=5)
    assert len(unread) == 2
    notif_id = unread[0]["id"]

    # Marcar una como leída
    db.mark_as_read(notif_id)
    assert db.get_unread_count(ROOT_ID) == 1

    # get_all_notifications trae tanto leídas como no leídas
    todas = db.get_all_notifications(ROOT_ID, limit=10, offset=0)
    assert len(todas) == 2

    # Marcar todas como leídas
    db.mark_all_as_read(ROOT_ID)
    assert db.get_unread_count(ROOT_ID) == 0
    assert db.get_unread_notifications(ROOT_ID) == []

    # Eliminar una notificación
    db.delete_notification(notif_id)
    assert len(db.get_all_notifications(ROOT_ID)) == 1


def test_tipo_notificacion_invalido_falla_por_check_constraint(db):
    """La tabla notifications solo acepta: info, warning, success, error."""
    with pytest.raises(DatabaseError):
        db.create_notification(ROOT_ID, "Título", "Msg", notification_type="invalido")