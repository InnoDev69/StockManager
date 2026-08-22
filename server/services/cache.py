import json
import os
from pathlib import Path
import tempfile
import time
from threading import Lock

from miscellaneous import logger, SCHEDULER, get_data_path

DATA_PATH = get_data_path("cache.json")


class CacheService:
    """
    Cache con expiración por entrada raíz y persistencia en disco.

    Cada entrada raíz se guarda como {"value": ..., "expires_at": epoch|None}.
    expires_at=None significa que no expira.

    --- Acceso anidado (dot-path) ---
    Igual que ConfigManager, se puede usar:
        cache.set("user.profile.name", "Juan")
        cache.get("user.profile.name")

    El PRIMER segmento del path es siempre la key raíz real (la que tiene
    expires_at). Los segmentos siguientes navegan dentro de su "value",
    que debe ser un dict. El TTL se aplica a la entrada raíz completa,
    no a cada sub-key individual.

    self.cache es siempre la fuente de verdad en runtime (se lee de ahí,
    nunca del archivo, salvo en el _load() inicial). Las escrituras a
    disco NO son inmediatas: cada cambio marca self._dirty = True, y un
    task del SCHEDULER vuelca a disco cada FLUSH_INTERVAL segundos si
    hay cambios pendientes. Esto evita pegarle al disco en cada set()
    cuando hay ráfagas de escrituras.

    Si necesitás la garantía de "esto ya está en disco" ANTES de seguir
    (ej: antes de un shutdown), llamá a flush() explícitamente.
    Se puede chequear cache.is_dirty() para saber si hay cambios sin persistir.
    """

    FLUSH_INTERVAL = 5  # segundos entre escrituras automáticas a disco

    def __init__(self, cache_file_path=None, default_timeout=60 * 60 * 24):
        self.cache = {}
        self.cache_file_path = Path(cache_file_path or DATA_PATH)
        self.timeout_cache = default_timeout
        self._lock = Lock()
        self._dirty = False
        self._load()
        SCHEDULER.add_task(60 * 60, self._garbage_collect)      # cada hora
        SCHEDULER.add_task(self.FLUSH_INTERVAL, self._flush_if_dirty)
        logger.info(f"CacheService inicializado con {len(self.cache)} entradas", source="CACHE_MODULE")

    # ---------- helpers de path ----------

    @staticmethod
    def _split_path(key_path):
        parts = key_path.split(".")
        return parts[0], parts[1:]

    @staticmethod
    def _get_nested(value, parts, default=None):
        node = value
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    @staticmethod
    def _set_nested(value, parts, leaf_value):
        """Modifica `value` in-place, creando dicts intermedios si hace falta."""
        node = value
        for part in parts[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                node[part] = nxt
            node = nxt
        node[parts[-1]] = leaf_value
        return value

    @staticmethod
    def _delete_nested(value, parts):
        node = value
        for part in parts[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                return False
            node = nxt
        return node.pop(parts[-1], None) is not None or parts[-1] in node

    def _get_live_entry(self, root_key):
        """Devuelve la entrada raíz si existe y no expiró; la descarta si expiró."""
        entry = self.cache.get(root_key)
        if entry is None:
            return None
        expires_at = entry.get("expires_at")
        if expires_at is not None and expires_at <= time.time():
            del self.cache[root_key]
            self._mark_dirty()
            logger.info(f"Entrada de cache expirada: {root_key}", source="CACHE_MODULE")
            return None
        return entry

    # ---------- persistencia ----------

    def _load(self):
        if not self.cache_file_path.exists():
            logger.info(f"Archivo de cache no existe, inicializando cache vacía: {self.cache_file_path}", source="CACHE_MODULE")
            return
        try:
            with open(self.cache_file_path, "r", encoding="utf-8") as f:
                logger.info(f"Cargando cache desde archivo: {self.cache_file_path}", source="CACHE_MODULE")
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Archivo de cache corrupto o ilegible, inicializando cache vacía: {self.cache_file_path}", source="CACHE_MODULE")
            self.cache = {}
            return

        if not isinstance(raw, dict):
            self.cache = {}
            logger.warning(f"Archivo de cache no es un dict, inicializando cache vacía: {self.cache_file_path}", source="CACHE_MODULE")
            return

        now = time.time()
        cache = {}
        for key, entry in raw.items():
            if not isinstance(entry, dict) or "value" not in entry:
                continue
            expires_at = entry.get("expires_at")
            if expires_at is not None and expires_at <= now:
                logger.info(f"Descartando entrada de cache expirada: {key}", source="CACHE_MODULE")
                continue
            cache[key] = entry
        self.cache = cache

    def _mark_dirty(self):
        self._dirty = True

    def is_dirty(self):
        """True si hay cambios en RAM que todavía no se escribieron a disco."""
        return self._dirty

    def _flush_if_dirty(self):
        if self._dirty:
            self._save()

    def flush(self):
        """Fuerza la escritura a disco ahora, sin esperar al scheduler."""
        if self._dirty:
            self._save()

    def _save(self):
        with self._lock:
            self.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=self.cache_file_path.parent, suffix=".tmp")
            logger.info(f"Guardando cache en archivo temporal: {tmp_path}", source="CACHE_MODULE")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.cache, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.cache_file_path)  # atómico
                self._dirty = False
                logger.info(f"Cache guardada en archivo: {self.cache_file_path}", source="CACHE_MODULE")
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                logger.error(f"Error al guardar cache en archivo: {self.cache_file_path}", source="CACHE_MODULE", exc_info=True)
                raise

    def _garbage_collect(self):
        now = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.get("expires_at") is not None and entry["expires_at"] <= now
        ]
        for key in expired_keys:
            del self.cache[key]
            logger.info(f"Entrada de cache expirada eliminada: {key}", source="CACHE_MODULE")
        if expired_keys:
            self._mark_dirty()

    # ---------- API pública ----------

    def get(self, key, default=None):
        root_key, rest = self._split_path(key)
        entry = self._get_live_entry(root_key)
        if entry is None:
            logger.info(f"Entrada de cache no encontrada: {key}", source="CACHE_MODULE")
            return default
        if not rest:
            return entry["value"]
        return self._get_nested(entry["value"], rest, default)

    def set(self, key, value, ttl=None):
        """
        ttl en segundos. None usa el default (self.timeout_cache).
        ttl<=0 guarda sin expiración.

        Con dot-path: el ttl se aplica a la entrada raíz completa.
        Si no se pasa ttl y la entrada raíz ya existía, se conserva
        su expiración actual (no se resetea el reloj por escribir
        una sub-key).
        """
        root_key, rest = self._split_path(key)

        if not rest:
            resolved_ttl = self.timeout_cache if ttl is None else ttl
            expires_at = (time.time() + resolved_ttl) if resolved_ttl and resolved_ttl > 0 else None
            self.cache[root_key] = {"value": value, "expires_at": expires_at}
        else:
            entry = self._get_live_entry(root_key)
            if entry is not None and isinstance(entry.get("value"), dict):
                base_value = entry["value"]
                expires_at = entry.get("expires_at") if ttl is None else (
                    (time.time() + ttl) if ttl > 0 else None
                )
            else:
                base_value = {}
                resolved_ttl = self.timeout_cache if ttl is None else ttl
                expires_at = (time.time() + resolved_ttl) if resolved_ttl and resolved_ttl > 0 else None
            self._set_nested(base_value, rest, value)
            self.cache[root_key] = {"value": base_value, "expires_at": expires_at}

        logger.info(
            f"Entrada de cache guardada: {key} (expira en {ttl} segundos)" if ttl else f"Entrada de cache guardada: {key}",
            source="CACHE_MODULE",
        )
        self._mark_dirty()

    def update(self, key, value, ttl=None):
        logger.info(f"Actualizando entrada de cache: {key}", source="CACHE_MODULE")
        self.set(key, value, ttl=ttl)

    def delete(self, key):
        root_key, rest = self._split_path(key)
        if not rest:
            if root_key in self.cache:
                del self.cache[root_key]
                self._mark_dirty()
            logger.info(f"Entrada de cache eliminada: {key}", source="CACHE_MODULE")
            return

        entry = self._get_live_entry(root_key)
        if entry is None or not isinstance(entry.get("value"), dict):
            return
        if self._delete_nested(entry["value"], rest):
            self._mark_dirty()
        logger.info(f"Entrada de cache eliminada: {key}", source="CACHE_MODULE")

    def clear(self):
        self.cache.clear()
        self._mark_dirty()
        self._save()  # clear() sí persiste inmediato, es un reset explícito
        logger.info("Cache limpiada", source="CACHE_MODULE")