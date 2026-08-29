"""
Manejo de contexto conversacional, liviano (en memoria).

Para producción real, cambiar el diccionario en memoria por Redis
u otro store persistente (la interfaz quedaría igual).
"""
import time
from collections import deque
from typing import Any, Deque, Dict, Optional


class Session:
    def __init__(self, session_id: str, history_size: int = 6):
        self.session_id = session_id
        self.history: Deque[dict] = deque(maxlen=history_size)
        self.slots: Dict[str, Any] = {}  # última entidad conocida por tipo (producto, cantidad...)
        self.last_intent: Optional[str] = None
        self.last_update = time.time()

    def push_turn(self, user_text: str, intent: Optional[str], entities: dict, bot_text: str):
        self.history.append(
            {
                "user": user_text,
                "intent": intent,
                "entities": entities,
                "bot": bot_text,
                "ts": time.time(),
            }
        )
        if entities:
            self.slots.update(entities)
        if intent:
            self.last_intent = intent
        self.last_update = time.time()

    def resolve_missing_entities(self, entities: dict, required: list) -> dict:
        """Completa entidades faltantes con las últimas conocidas en la sesión.
        Permite manejar cosas como: '¿y el precio?' después de preguntar por un producto.
        """
        resolved = dict(entities)
        for key in required:
            if key not in resolved and key in self.slots:
                resolved[key] = self.slots[key]
        return resolved


class ContextManager:
    def __init__(self, session_timeout_sec: int = 60 * 30):
        self.sessions: Dict[str, Session] = {}
        self.session_timeout_sec = session_timeout_sec

    def get_session(self, session_id: str) -> Session:
        self._cleanup()
        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id)
        return self.sessions[session_id]

    def _cleanup(self):
        now = time.time()
        expired = [
            sid
            for sid, s in self.sessions.items()
            if now - s.last_update > self.session_timeout_sec
        ]
        for sid in expired:
            del self.sessions[sid]
