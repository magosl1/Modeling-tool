"""Tests for Fase 0 — security hardening.

Covers:
- No dev backdoor in auth.login
- SECRET_KEY runtime validation (length + insecure list, even in DEBUG)
- CORS_ORIGINS validation in production mode
"""
from __future__ import annotations

import importlib

import pytest


# ---------------------------------------------------------------------------
# Backdoor removal
# ---------------------------------------------------------------------------

class TestNoDevBackdoor:
    def test_auth_source_does_not_contain_backdoor_email(self):
        """The hardcoded magosl1@hotmail.com / 12345678 backdoor must be gone."""
        from pathlib import Path

        auth_path = Path(__file__).resolve().parents[2] / "app" / "api" / "routes" / "auth.py"
        source = auth_path.read_text(encoding="utf-8")

        assert "magosl1@hotmail.com" not in source, (
            "Dev backdoor email still present in auth.py"
        )
        assert "12345678" not in source, (
            "Dev backdoor password still present in auth.py"
        )
        assert "DEV BACKDOOR" not in source.upper(), (
            "Dev backdoor comment marker still present in auth.py"
        )
        assert "Master User" not in source, (
            "Master User backdoor identity still present in auth.py"
        )


# ---------------------------------------------------------------------------
# SECRET_KEY validation
# ---------------------------------------------------------------------------

def _build_settings(**overrides):
    """Instantiate Settings with explicit overrides bypassing the env file."""
    from app.core.config import Settings

    base = {
        "SECRET_KEY": "x" * 64,
        "DEBUG": True,
        "CORS_ORIGINS": "http://localhost:5173",
    }
    base.update(overrides)
    return Settings(**base)


class TestSecretKeyValidation:
    def test_insecure_default_rejected_in_debug(self):
        s = _build_settings(SECRET_KEY="change-me-in-production", DEBUG=True)
        with pytest.raises(RuntimeError, match="insecure default"):
            s.validate_runtime()

    def test_insecure_default_rejected_in_production(self):
        s = _build_settings(
            SECRET_KEY="change-me-in-production",
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com",
        )
        with pytest.raises(RuntimeError, match="insecure default"):
            s.validate_runtime()

    def test_short_key_rejected_even_in_debug(self):
        s = _build_settings(SECRET_KEY="x" * 31, DEBUG=True)
        with pytest.raises(RuntimeError, match="too short"):
            s.validate_runtime()

    def test_minimum_length_passes(self):
        s = _build_settings(SECRET_KEY="x" * 32, DEBUG=True)
        s.validate_runtime()  # should not raise

    def test_strong_key_passes(self):
        s = _build_settings(
            SECRET_KEY="kj3l4kj3l4kj3l4kj3l4kj3l4kj3l4kj3l4kj3l4kj3l4kj3l4",
            DEBUG=True,
        )
        s.validate_runtime()  # should not raise


# ---------------------------------------------------------------------------
# CORS validation
# ---------------------------------------------------------------------------

class TestCorsValidation:
    def test_localhost_rejected_in_production(self):
        s = _build_settings(
            DEBUG=False,
            CORS_ORIGINS="http://localhost:5173,https://app.example.com",
        )
        with pytest.raises(RuntimeError, match="localhost"):
            s.validate_runtime()

    def test_127_0_0_1_rejected_in_production(self):
        s = _build_settings(
            DEBUG=False,
            CORS_ORIGINS="http://127.0.0.1:5173",
        )
        with pytest.raises(RuntimeError, match="localhost"):
            s.validate_runtime()

    def test_wildcard_rejected_in_production(self):
        s = _build_settings(DEBUG=False, CORS_ORIGINS="*")
        with pytest.raises(RuntimeError, match="not allowed"):
            s.validate_runtime()

    def test_empty_origins_rejected_in_production(self):
        s = _build_settings(DEBUG=False, CORS_ORIGINS="")
        with pytest.raises(RuntimeError, match="must be set"):
            s.validate_runtime()

    def test_explicit_https_origin_passes_in_production(self):
        s = _build_settings(
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com,https://staging.example.com",
        )
        s.validate_runtime()  # should not raise

    def test_localhost_allowed_in_debug(self):
        s = _build_settings(
            DEBUG=True,
            CORS_ORIGINS="http://localhost:5173,http://localhost:3000",
        )
        s.validate_runtime()  # should not raise

    def test_origins_list_parsing(self):
        s = _build_settings(
            CORS_ORIGINS=" http://a.com , http://b.com ,, http://c.com ",
        )
        assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]


# ---------------------------------------------------------------------------
# Module-level settings instance
# ---------------------------------------------------------------------------

class TestModuleLevelSettings:
    def test_module_level_settings_passes_validation(self):
        """The `settings` instance imported at module load must validate."""
        from app.core import config

        importlib.reload(config)
        # If this raised, conftest.py would have failed to import the module.
        assert config.settings.SECRET_KEY
        assert len(config.settings.SECRET_KEY) >= 32
