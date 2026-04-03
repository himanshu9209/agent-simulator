"""
tests/test_cli.py
Verify CLI argument parsing, dry-run output, config overrides, and error paths.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from simulator.cli import build_parser, _print_dry_run, _apply_overrides
from simulator.config import (
    AgentProfile,
    GaussianDistribution,
    RootConfig,
    ScenarioConfig,
    SimulatorConfig,
    TelemetryConfig,
    TlsConfig,
    UniformIntDistribution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_profile(**overrides) -> AgentProfile:
    defaults = dict(
        tools=["search", "summarise"],
        llm_model="gpt-4o",
        llm_input_tokens=GaussianDistribution(mean=500, std=100),
        llm_output_tokens=GaussianDistribution(mean=100, std=20),
        planning_latency_ms=GaussianDistribution(mean=100, std=10),
        tool_call_count=UniformIntDistribution(min=1, max=3),
    )
    defaults.update(overrides)
    return AgentProfile(**defaults)


def _minimal_config(**overrides) -> RootConfig:
    defaults = dict(
        simulator=SimulatorConfig(
            concurrency=5,
            run_duration_seconds=60,
            clock_multiplier=2.0,
            random_seed=42,
        ),
        telemetry=TelemetryConfig(exporter_endpoint="http://localhost:4317"),
        agent_profiles={"test_agent": _minimal_profile()},
    )
    defaults.update(overrides)
    return RootConfig(**defaults)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_default_config(self):
        args = build_parser().parse_args([])
        assert args.config == "config/default.yaml"

    def test_short_config_flag(self):
        args = build_parser().parse_args(["-c", "my.yaml"])
        assert args.config == "my.yaml"

    def test_long_config_flag(self):
        args = build_parser().parse_args(["--config", "path/to/config.yaml"])
        assert args.config == "path/to/config.yaml"

    def test_dry_run_default_false(self):
        args = build_parser().parse_args([])
        assert args.dry_run is False

    def test_dry_run_flag(self):
        args = build_parser().parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_profile_default_none(self):
        args = build_parser().parse_args([])
        assert args.profile is None

    def test_profile_flag(self):
        args = build_parser().parse_args(["--profile", "rag_researcher"])
        assert args.profile == "rag_researcher"

    def test_duration_default_none(self):
        args = build_parser().parse_args([])
        assert args.duration is None

    def test_duration_flag(self):
        args = build_parser().parse_args(["--duration", "120"])
        assert args.duration == 120

    def test_concurrency_default_none(self):
        args = build_parser().parse_args([])
        assert args.concurrency is None

    def test_concurrency_flag(self):
        args = build_parser().parse_args(["--concurrency", "50"])
        assert args.concurrency == 50

    def test_no_console_default_false(self):
        args = build_parser().parse_args([])
        assert args.no_console is False

    def test_no_console_flag(self):
        args = build_parser().parse_args(["--no-console"])
        assert args.no_console is True

    def test_all_flags_together(self):
        args = build_parser().parse_args([
            "-c", "config/prod.yaml",
            "--dry-run",
            "--profile", "rag_researcher",
            "--duration", "300",
            "--concurrency", "100",
            "--no-console",
        ])
        assert args.config == "config/prod.yaml"
        assert args.dry_run is True
        assert args.profile == "rag_researcher"
        assert args.duration == 300
        assert args.concurrency == 100
        assert args.no_console is True


# ---------------------------------------------------------------------------
# Dry-run printer
# ---------------------------------------------------------------------------

class TestPrintDryRun:
    def test_shows_dry_run_header(self, capsys):
        _print_dry_run(_minimal_config(), "config/test.yaml")
        assert "Dry Run" in capsys.readouterr().out

    def test_shows_config_path(self, capsys):
        _print_dry_run(_minimal_config(), "config/my_agent.yaml")
        assert "config/my_agent.yaml" in capsys.readouterr().out

    def test_shows_concurrency(self, capsys):
        cfg = _minimal_config(
            simulator=SimulatorConfig(concurrency=42, run_duration_seconds=60,
                                      clock_multiplier=1.0)
        )
        _print_dry_run(cfg, "test.yaml")
        assert "42 agents" in capsys.readouterr().out

    def test_shows_otel_endpoint(self, capsys):
        cfg = _minimal_config(
            telemetry=TelemetryConfig(exporter_endpoint="http://collector:4317")
        )
        _print_dry_run(cfg, "test.yaml")
        assert "http://collector:4317" in capsys.readouterr().out

    def test_shows_profile_name(self, capsys):
        _print_dry_run(_minimal_config(), "test.yaml")
        assert "test_agent" in capsys.readouterr().out

    def test_shows_valid_confirmation(self, capsys):
        _print_dry_run(_minimal_config(), "test.yaml")
        assert "Config valid" in capsys.readouterr().out

    def test_shows_auth_headers_when_present(self, capsys):
        cfg = _minimal_config(
            telemetry=TelemetryConfig(
                exporter_endpoint="http://localhost:4317",
                headers={"x-api-key": "${MY_KEY}"},
            )
        )
        _print_dry_run(cfg, "test.yaml")
        assert "x-api-key" in capsys.readouterr().out

    def test_shows_tls_when_enabled(self, capsys):
        cfg = _minimal_config(
            telemetry=TelemetryConfig(
                exporter_endpoint="https://api.honeycomb.io:443",
                tls=TlsConfig(insecure=False),
            )
        )
        _print_dry_run(cfg, "test.yaml")
        assert "TLS" in capsys.readouterr().out

    def test_shows_pricing_models_when_present(self, capsys):
        from simulator.config import ModelPricing
        cfg = _minimal_config(
            pricing={"gpt-4o": ModelPricing(input_per_million=2.5, output_per_million=10.0)}
        )
        _print_dry_run(cfg, "test.yaml")
        assert "gpt-4o" in capsys.readouterr().out

    def test_shows_scenarios_when_present(self, capsys):
        cfg = _minimal_config(
            scenarios=ScenarioConfig(enabled={"tool_timeout": 0.05})
        )
        _print_dry_run(cfg, "test.yaml")
        assert "tool_timeout" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _apply_overrides
# ---------------------------------------------------------------------------

class TestApplyOverrides:
    def _args(self, **kwargs):
        """Build a minimal Namespace-like object."""
        import argparse
        defaults = dict(duration=None, concurrency=None, profile=None)
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_duration_override(self):
        cfg = _minimal_config()
        result = _apply_overrides(cfg, self._args(duration=30))
        assert result.simulator.run_duration_seconds == 30

    def test_concurrency_override(self):
        cfg = _minimal_config()
        result = _apply_overrides(cfg, self._args(concurrency=10))
        assert result.simulator.concurrency == 10

    def test_both_overrides(self):
        cfg = _minimal_config()
        result = _apply_overrides(cfg, self._args(duration=15, concurrency=3))
        assert result.simulator.run_duration_seconds == 15
        assert result.simulator.concurrency == 3

    def test_profile_filter(self):
        cfg = _minimal_config(
            agent_profiles={
                "alpha": _minimal_profile(),
                "beta": _minimal_profile(),
            }
        )
        result = _apply_overrides(cfg, self._args(profile="alpha"))
        assert list(result.agent_profiles.keys()) == ["alpha"]

    def test_original_config_not_mutated(self):
        cfg = _minimal_config()
        original_duration = cfg.simulator.run_duration_seconds
        _apply_overrides(cfg, self._args(duration=999))
        assert cfg.simulator.run_duration_seconds == original_duration

    def test_unknown_profile_exits(self):
        cfg = _minimal_config()
        with pytest.raises(SystemExit):
            _apply_overrides(cfg, self._args(profile="nonexistent"))

    def test_no_overrides_returns_equivalent_config(self):
        cfg = _minimal_config()
        result = _apply_overrides(cfg, self._args())
        assert result.simulator.concurrency == cfg.simulator.concurrency
        assert result.simulator.run_duration_seconds == cfg.simulator.run_duration_seconds
