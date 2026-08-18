import json
import os
import tempfile
from pathlib import Path
from threading import Lock

from miscellaneous import logger

LOGGER_NAME = "CONFIG_MANAGER"

class DotDict(dict):
    """Permite acceso tipo a.b.c sobre un dict anidado sin perder compatibilidad con dict normal."""

    def __getattr__(self, key):
        try:
            value = self[key]
        except KeyError:
            raise AttributeError(key)
        return DotDict(value) if isinstance(value, dict) else value

    def __setattr__(self, key, value):
        self[key] = value


class ConfigManager:
    """
    Singleton de configuración. Cada módulo de la app (backup, telemetría, etc.)
    registra sus propios defaults con register_defaults() sin tocar este archivo.
    """

    _instance = None
    _instance_lock = Lock()
    _defaults_registry = {}
    _migrations = []  # [(target_version, fn(data) -> data), ...]
    _ignored_keys = [
        "ui",
        "app"
        ]  # keys que no se guardan en el config.json (ej: passwords)

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path=None):
        logger.info("Initializing ConfigManager", source=LOGGER_NAME)
        
        if self._initialized:
            return
        if config_path is None:
            raise ValueError("Config path must be provided on first initialization")
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = Lock()
        self._data = {}
        self._initialized = True
        self.reload()
        logger.info(f"ConfigManager initialized with config path: {self.config_path}", source=LOGGER_NAME)

    # ---------- registro modular ----------

    @classmethod
    def register_defaults(cls, namespace: str, defaults: dict):
        """Cada módulo llama esto al importarse, ej: ConfigManager.register_defaults('backup', {...})"""
        logger.debug(f"Registering defaults for namespace: {namespace}", source=LOGGER_NAME)
        cls._defaults_registry[namespace] = defaults

    @classmethod
    def register_migration(cls, target_version: int, fn):
        """Para cambios que rompen compatibilidad (ej: renombrar una key existente)."""
        logger.debug(f"Registering migration for version: {target_version}", source=LOGGER_NAME)
        cls._migrations.append((target_version, fn))

    @classmethod
    def current_version(cls):
        """Devuelve la versión más alta de migración registrada, o 1 si no hay migraciones."""
        logger.debug("Getting current version", source=LOGGER_NAME)
        return max((v for v, _ in cls._migrations), default=0)
    
    @classmethod
    def migration(cls, target_version: int):
        """Decorador para registrar una función de migración. Ej:
        @ConfigManager.migration(2)
        def migrate_to_v2(data):
            ...
        """
        logger.debug(f"Registering migration for version: {target_version}", source=LOGGER_NAME)
        def decorator(fn):
            if any(v == target_version for v, _ in cls._migrations):
                raise ValueError(f"Ya existe una migración registrada para la versión {target_version}")
            cls.register_migration(target_version, fn)
            return fn
        return decorator

    # ---------- carga y persistencia ----------

    def _build_defaults(self):
        """Devuelve un dict con todos los defaults registrados por los módulos."""
        logger.debug("Building defaults from registered modules", source=LOGGER_NAME)
        return json.loads(json.dumps(self._defaults_registry))  # deep copy
    
    def _ignore_keys(self, data):
        """Elimina del dict las keys que no deben cargarse y guardarse en el config.json"""
        logger.debug("Ignoring keys in data", source=LOGGER_NAME)
        if isinstance(data, dict):
            return {k: self._ignore_keys(v) for k, v in data.items() if k not in self._ignored_keys}
        elif isinstance(data, list):
            return [self._ignore_keys(v) for v in data]
        else:
            return data

    def reload(self):
        """Carga el config.json, aplica migraciones y mergea con los defaults."""
        logger.info("Reloading configuration", source=LOGGER_NAME)
        defaults = self._build_defaults()

        if not self.config_path.exists():
            data = defaults
            data["_version"] = self.current_version()
            self._write(data)
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = defaults
                data["_version"] = self.current_version()
                self._write(data)

        data = self._apply_migrations(data)
        self._data = self._deep_merge(defaults, data)
        return self._data

    def _apply_migrations(self, data):
        """Aplica las migraciones registradas en orden ascendente de versión."""
        logger.debug("Applying migrations to configuration data", source=LOGGER_NAME)
        version = data.get("_version", 0)
        changed = False
        for target_version, fn in sorted(self._migrations, key=lambda x: x[0]):
            if version < target_version:
                data = fn(data)
                version = target_version
                changed = True
        data["_version"] = version
        if changed:
            self._write(data)
        return data

    def _deep_merge(self, base, override):
        """Mergea dos dicts anidados, override tiene prioridad sobre base."""
        logger.debug("Merging configuration data", source=LOGGER_NAME)
        merged = json.loads(json.dumps(base))

        def merge(b, o):
            for k, v in o.items():
                if isinstance(v, dict) and isinstance(b.get(k), dict):
                    merge(b[k], v)
                else:
                    b[k] = v

        merge(merged, override)
        return merged

    def _write(self, data):
        """Escribe el config.json de manera atómica."""
        logger.debug("Writing configuration to file", source=LOGGER_NAME)
        with self._write_lock:
            fd, tmp_path = tempfile.mkstemp(dir=self.config_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.config_path)  # atómico
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise
        logger.info("Configuration written to file", source=LOGGER_NAME)

    # ---------- API pública ----------
    def get_all(self, filter: list = None, exclude: list = None):
        data = self._data
        if filter:
            data = {k: v for k, v in data.items() if k in filter}
        if exclude:
            data = {k: v for k, v in data.items() if k not in exclude}
        return DotDict(data)

    def get(self, key_path: str, filter:list=None, exclude:list=None,default=None):
        """config.get('backup.s3.bucket')"""
        node = self._data
        for part in key_path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        if filter:
            node = {k: v for k, v in node.items() if k in filter}
        if exclude:
            node = {k: v for k, v in node.items() if k not in exclude}
        return DotDict(node) if isinstance(node, dict) else node

    def set(self, key_path: str, value):
        """config.set('backup.frequency_days', 14)"""
        parts = key_path.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self._write(self._data)

    def __getattr__(self, name):
        """Permite config.backup.auto_enabled directamente"""
        if name.startswith("_"):
            raise AttributeError(name)
        data = object.__getattribute__(self, "_data")
        if name in data:
            value = data[name]
            return DotDict(value) if isinstance(value, dict) else value
        raise AttributeError(name)

    def all(self):
        return DotDict(self._data)