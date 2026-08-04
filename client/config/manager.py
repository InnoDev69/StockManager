import json
import os
import tempfile
from pathlib import Path
from threading import Lock


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

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path=None):
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

    # ---------- registro modular ----------

    @classmethod
    def register_defaults(cls, namespace: str, defaults: dict):
        """Cada módulo llama esto al importarse, ej: ConfigManager.register_defaults('backup', {...})"""
        cls._defaults_registry[namespace] = defaults

    @classmethod
    def register_migration(cls, target_version: int, fn):
        """Para cambios que rompen compatibilidad (ej: renombrar una key existente)."""
        cls._migrations.append((target_version, fn))

    @classmethod
    def current_version(cls):
        return max((v for v, _ in cls._migrations), default=1)

    # ---------- carga y persistencia ----------

    def _build_defaults(self):
        return json.loads(json.dumps(self._defaults_registry))  # deep copy

    def reload(self):
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

    # ---------- API pública ----------
    def get_all(self):
        return DotDict(self._data)

    def get(self, key_path: str, default=None):
        """config.get('backup.s3.bucket')"""
        node = self._data
        for part in key_path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
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