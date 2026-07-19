import pytest

from config import ConfigError, Settings


@pytest.fixture
def clean_env(monkeypatch):
    # Wipe any WMI_*/API keys so tests are deterministic regardless of the .env file.
    import os

    for key in list(os.environ):
        if key.startswith("WMI_") or key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_missing_api_key_raises(clean_env):
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_defaults(clean_env):
    clean_env.setenv("GOOGLE_API_KEY", "AIza_test")
    s = Settings.from_env()
    s.validate()
    assert s.news.model == "gemini-2.5-flash"
    assert s.quant.model == "gemini-2.5-flash"
    assert s.highlight_count == 6
    assert s.shortlist_count == 10
    assert s.min_valid_candidates == 8
    assert s.fetch.max_workers >= 1


def test_gemini_api_key_alias(clean_env):
    clean_env.setenv("GEMINI_API_KEY", "AIza_alias")
    s = Settings.from_env()
    assert s.api_key == "AIza_alias"


def test_env_overrides(clean_env):
    clean_env.setenv("GOOGLE_API_KEY", "AIza_test")
    clean_env.setenv("WMI_NEWS_MODEL", "some/other-model")
    clean_env.setenv("WMI_HIGHLIGHT_COUNT", "4")
    clean_env.setenv("WMI_MIN_VALID_CANDIDATES", "6")
    clean_env.setenv("WMI_TARGET_CANDIDATES", "12")
    s = Settings.from_env()
    s.validate()
    assert s.news.model == "some/other-model"
    assert s.highlight_count == 4


def test_validate_rejects_inconsistent(clean_env):
    clean_env.setenv("GOOGLE_API_KEY", "AIza_test")
    clean_env.setenv("WMI_TARGET_CANDIDATES", "3")
    clean_env.setenv("WMI_MIN_VALID_CANDIDATES", "5")
    s = Settings.from_env()
    with pytest.raises(ConfigError):
        s.validate()


def test_validate_rejects_shortlist_below_highlight(clean_env):
    clean_env.setenv("GOOGLE_API_KEY", "AIza_test")
    clean_env.setenv("WMI_SHORTLIST_COUNT", "2")
    clean_env.setenv("WMI_HIGHLIGHT_COUNT", "3")
    s = Settings.from_env()
    with pytest.raises(ConfigError):
        s.validate()


def test_bad_int_raises(clean_env):
    clean_env.setenv("GOOGLE_API_KEY", "AIza_test")
    clean_env.setenv("WMI_HIGHLIGHT_COUNT", "three")
    with pytest.raises(ConfigError):
        Settings.from_env()
