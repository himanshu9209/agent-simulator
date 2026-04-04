"""
simulator/api/config_manager.py
Thread-safe reader/writer for the simulator config YAML file.

Rules:
  - Never writes an invalid config (validates first).
  - Creates a timestamped backup before every write.
  - Keeps at most MAX_BACKUPS backups in config/.backups/.
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import List

import yaml
from pydantic import ValidationError

from simulator.config import RootConfig, load_config


class ConfigManager:
    """Thread-safe reader/writer for a simulator config YAML file."""

    MAX_BACKUPS: int = 5

    def __init__(self, config_path: str | Path = "config/default.yaml") -> None:
        self._path = Path(config_path)
        self._backup_dir = self._path.parent / ".backups"
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self) -> RootConfig:
        """Load and validate the config file, returning a RootConfig."""
        with self._lock:
            return load_config(self._path)

    def read_raw(self) -> str:
        """Return the raw YAML text of the config file."""
        with self._lock:
            return self._path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate_raw(self, yaml_str: str) -> List[str]:
        """
        Validate a YAML string against the RootConfig schema.
        Returns a list of human-readable error strings; empty list means valid.
        """
        try:
            raw = yaml.safe_load(yaml_str)
        except yaml.YAMLError as exc:
            return [f"YAML parse error: {exc}"]
        if raw is None or not isinstance(raw, dict):
            return ["Config must be a non-empty YAML mapping"]
        try:
            RootConfig.model_validate(raw)
            return []
        except ValidationError as exc:
            return [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, cfg: RootConfig) -> None:
        """
        Serialize a RootConfig to YAML and overwrite the config file.
        Creates a backup first.
        """
        with self._lock:
            # Serialise through JSON to ensure clean Python primitives for yaml.dump
            data = json.loads(cfg.model_dump_json(exclude_none=True))
            yaml_str = yaml.dump(
                data, default_flow_style=False, sort_keys=False, allow_unicode=True
            )
            self.backup()
            self._path.write_text(yaml_str, encoding="utf-8")

    def write_raw(self, yaml_str: str) -> None:
        """
        Validate a raw YAML string, then overwrite the config file.
        Raises ValueError (with the error list) if validation fails.
        """
        errors = self.validate_raw(yaml_str)
        if errors:
            raise ValueError(errors)
        with self._lock:
            self.backup()
            self._path.write_text(yaml_str, encoding="utf-8")

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def backup(self) -> Path:
        """
        Copy the current config to <config_dir>/.backups/ with a timestamp suffix.
        Prunes backups beyond MAX_BACKUPS (oldest first).
        Returns the path of the newly created backup file.
        """
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        stem = self._path.stem
        backup_path = self._backup_dir / f"{stem}_{timestamp}.yaml"
        shutil.copy2(self._path, backup_path)
        # Prune oldest backups beyond the limit
        existing = sorted(self._backup_dir.glob(f"{stem}_*.yaml"))
        for old in existing[: -self.MAX_BACKUPS]:
            old.unlink()
        return backup_path
