"""
tests/test_config_manager.py
Tests for ConfigManager: read, validate, write_raw, write, backup, thread safety.
"""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import pytest
import yaml

from simulator.api.config_manager import ConfigManager
from simulator.config import RootConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_file(tmp_path) -> Path:
    src = Path("config/default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    return dst


@pytest.fixture
def manager(config_file) -> ConfigManager:
    return ConfigManager(config_file)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class TestRead:
    def test_read_returns_root_config(self, manager):
        cfg = manager.read()
        assert isinstance(cfg, RootConfig)

    def test_read_has_profiles(self, manager):
        cfg = manager.read()
        assert len(cfg.agent_profiles) > 0

    def test_read_raw_returns_string(self, manager):
        raw = manager.read_raw()
        assert isinstance(raw, str)
        assert "agent_profiles" in raw

    def test_path_property(self, manager, config_file):
        assert manager.path == config_file


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

class TestValidateRaw:
    def test_valid_yaml_returns_empty_list(self, manager):
        raw = manager.read_raw()
        errors = manager.validate_raw(raw)
        assert errors == []

    def test_yaml_syntax_error_returns_error(self, manager):
        errors = manager.validate_raw("key: [unclosed")
        assert len(errors) > 0
        assert any("YAML" in e or "parse" in e.lower() for e in errors)

    def test_missing_required_field_returns_errors(self, manager):
        # agent_profiles is required; omitting it should fail
        bad = yaml.dump({"simulator": {"concurrency": 1, "run_duration_seconds": 10,
                                        "clock_multiplier": 1.0}})
        errors = manager.validate_raw(bad)
        assert len(errors) > 0

    def test_non_dict_yaml_returns_error(self, manager):
        errors = manager.validate_raw("- just\n- a\n- list")
        assert len(errors) > 0

    def test_empty_string_returns_error(self, manager):
        errors = manager.validate_raw("")
        assert len(errors) > 0

    def test_null_yaml_returns_error(self, manager):
        errors = manager.validate_raw("null")
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# write_raw
# ---------------------------------------------------------------------------

class TestWriteRaw:
    def test_valid_yaml_updates_file(self, manager, config_file):
        raw = manager.read_raw()
        modified = raw.replace("concurrency: 200", "concurrency: 10")
        manager.write_raw(modified)
        assert "concurrency: 10" in config_file.read_text(encoding="utf-8")

    def test_invalid_yaml_raises_value_error(self, manager):
        with pytest.raises(ValueError):
            manager.write_raw("not: valid: yaml: [")

    def test_invalid_yaml_does_not_modify_file(self, manager, config_file):
        original = config_file.read_text(encoding="utf-8")
        try:
            manager.write_raw("broken: [yaml")
        except ValueError:
            pass
        assert config_file.read_text(encoding="utf-8") == original

    def test_write_raw_creates_backup(self, manager, config_file):
        raw = manager.read_raw()
        manager.write_raw(raw)
        backups = list((config_file.parent / ".backups").glob("*.yaml"))
        assert len(backups) >= 1


# ---------------------------------------------------------------------------
# write (RootConfig)
# ---------------------------------------------------------------------------

class TestWrite:
    def test_roundtrip_preserves_profiles(self, manager):
        cfg = manager.read()
        original_names = set(cfg.agent_profiles.keys())
        manager.write(cfg)
        reloaded = manager.read()
        assert set(reloaded.agent_profiles.keys()) == original_names

    def test_write_creates_backup(self, manager, config_file):
        cfg = manager.read()
        manager.write(cfg)
        backups = list((config_file.parent / ".backups").glob("*.yaml"))
        assert len(backups) >= 1

    def test_reloaded_config_is_valid(self, manager):
        cfg = manager.read()
        manager.write(cfg)
        reloaded = manager.read()
        assert isinstance(reloaded, RootConfig)


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

class TestBackup:
    def test_backup_creates_file(self, manager, config_file):
        backup_path = manager.backup()
        assert backup_path.exists()

    def test_backup_in_correct_directory(self, manager, config_file):
        backup_path = manager.backup()
        assert backup_path.parent == config_file.parent / ".backups"

    def test_backup_contains_original_content(self, manager):
        original = manager.read_raw()
        backup_path = manager.backup()
        assert backup_path.read_text(encoding="utf-8") == original

    def test_backup_prunes_to_max_5(self, manager):
        for _ in range(8):
            time.sleep(0.005)  # distinct timestamps
            manager.backup()
        backup_dir = manager.path.parent / ".backups"
        backups = list(backup_dir.glob("*.yaml"))
        assert len(backups) <= ConfigManager.MAX_BACKUPS

    def test_backup_stem_matches_config_file(self, manager, config_file):
        backup_path = manager.backup()
        assert backup_path.name.startswith(config_file.stem)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_reads_do_not_raise(self, manager):
        errors: list = []

        def read():
            try:
                manager.read()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=read) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_writes_produce_valid_config(self, manager):
        errors: list = []

        def write():
            try:
                cfg = manager.read()
                manager.write(cfg)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=write) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # Config must still be valid after concurrent writes
        assert isinstance(manager.read(), RootConfig)
