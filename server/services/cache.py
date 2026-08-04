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
    Cache simple con expiración por entrada y persistencia en disco.

    Cada entrada se guarda como {"value": ..., "expires_at": epoch|None}.
    expires_at=None significa que no expira (se guarda igual, pero nunca
    se descarta por tiempo).
    """

    def __init__(self, cache_file_path=None, default_timeout=60 * 60 * 24):
        self.cache = {}
        # Path(...) normaliza tanto si nos pasan un str como un Path —
        # get_app_dir() (o quien llame al constructor) puede devolver
        # cualquiera de los dos según la implementación.
        self.cache_file_path = Path(cache_file_path or DATA_PATH)
        self.timeout_cache = default_timeout  # 24 horas por default
        self._lock = Lock()
        self._load()
        SCHEDULER.add_task(60 * 60, self._garbage_collect)  # cada hora
        logger.info(f"CacheService inicializado con {len(self.cache)} entradas", source="CACHE_MODULE")

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
            # Archivo corrupto o ilegible: arrancamos con cache vacía
            # en vez de romper el arranque de la app.
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
                continue  # expiró mientras la app estaba cerrada
            cache[key] = entry
        self.cache = cache

    def _save(self):
        with self._lock:
            self.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=self.cache_file_path.parent, suffix=".tmp"
            )
            logger.info(f"Guardando cache en archivo temporal: {tmp_path}", source="CACHE_MODULE")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.cache, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.cache_file_path)  # atómico
                logger.info(f"Cache guardada en archivo: {self.cache_file_path}", source="CACHE_MODULE")
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                logger.error(f"Error al guardar cache en archivo: {self.cache_file_path}", source="CACHE_MODULE", exc_info=True)
                raise
            
    def _garbage_collect(self):
        now = time.time()
        expired_keys = [key for key, entry in self.cache.items() if entry.get("expires_at") is not None and entry["expires_at"] <= now]
        for key in expired_keys:
            del self.cache[key]
            logger.info(f"Entrada de cache expirada eliminada: {key}", source="CACHE_MODULE")
        if expired_keys:
            self._save()

    # ---------- API pública ----------

    def get(self, key, default=None):
        entry = self.cache.get(key)
        if entry is None:
            logger.info(f"Entrada de cache no encontrada: {key}", source="CACHE_MODULE")
            return default

        expires_at = entry.get("expires_at")
        if expires_at is not None and expires_at <= time.time():
            # Expiró desde que se cargó en memoria: la sacamos y
            # persistimos el descarte para no repetir el chequeo.
            del self.cache[key]
            self._save()
            logger.info(f"Entrada de cache expirada: {key}", source="CACHE_MODULE")
            return default

        return entry["value"]

    def set(self, key, value, ttl=None):
        """
        ttl en segundos. None usa el default (self.timeout_cache).
        Pasar ttl=0 (o un valor <= 0) guarda la entrada sin expiración.
        """
        if ttl is None:
            ttl = self.timeout_cache
        expires_at = (time.time() + ttl) if ttl and ttl > 0 else None

        self.cache[key] = {"value": value, "expires_at": expires_at}
        logger.info(f"Entrada de cache guardada: {key} (expira en {ttl} segundos)" if expires_at else f"Entrada de cache guardada: {key} (sin expiración)", source="CACHE_MODULE")  
        self._save()

    def update(self, key, value, ttl=None):
        logger.info(f"Actualizando entrada de cache: {key}", source="CACHE_MODULE")
        self.set(key, value, ttl=ttl)

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]
            self._save()
        logger.info(f"Entrada de cache eliminada: {key}", source="CACHE_MODULE")

    def clear(self):
        self.cache.clear()
        self._save()
        logger.info("Cache limpiada", source="CACHE_MODULE")