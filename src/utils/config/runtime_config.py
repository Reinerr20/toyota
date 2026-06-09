import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

log = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME_CONFIG_PATH = PROJECT_ROOT / "config" / "runtime_config.yaml"


class RuntimeConfig:
    """
    Runtime/device/server configuration with priority:
      1. environment variable override
      2. config/runtime_config.yaml
      3. hardcoded fallback
    """

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else DEFAULT_RUNTIME_CONFIG_PATH
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path
        self.data = self._load()

    def get(self, dotted_path: str, default: Any = None, env: Optional[str] = None) -> Any:
        if env and os.getenv(env) is not None:
            return os.getenv(env)

        node: Any = self.data
        for key in dotted_path.split("."):
            if not isinstance(node, dict):
                return default
            node = node.get(key)
            if node is None:
                return default
        return node

    def get_str(self, dotted_path: str, default: str, env: Optional[str] = None) -> str:
        return str(self.get(dotted_path, default, env=env))

    def get_int(self, dotted_path: str, default: int, env: Optional[str] = None) -> int:
        return int(self.get(dotted_path, default, env=env))

    def get_float(self, dotted_path: str, default: float, env: Optional[str] = None) -> float:
        return float(self.get(dotted_path, default, env=env))

    def get_bool(self, dotted_path: str, default: bool, env: Optional[str] = None) -> bool:
        return self._to_bool(self.get(dotted_path, default, env=env))

    def project_path(self, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str(PROJECT_ROOT / path)

    def display_path(self) -> str:
        try:
            return str(self.path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(self.path)

    def _load(self) -> dict:
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                return raw if isinstance(raw, dict) else {}
            log.warning("[CONFIG] runtime config missing: %s", self.path)
        except Exception as e:
            log.warning("[CONFIG] failed to load runtime config %s: %s", self.path, e)
        return {}

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
