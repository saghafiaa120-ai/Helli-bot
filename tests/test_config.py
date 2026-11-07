import pytest

from core.config import ConfigError, load_settings, parse_env_file, to_sync_url

TOKEN = "123456789:AAExampleTokenExampleTokenExample123"
DB = "mysql+asyncmy://u:p@127.0.0.1:3306/helli?charset=utf8mb4"


def _load(tmp_path, env_text="", environ=None, **kwargs):
    env_file = tmp_path / ".env"
    env_file.write_text(env_text, encoding="utf-8")
    return load_settings(env_file, environ or {}, **kwargs)


def test_loads_from_env_file(tmp_path):
    settings = _load(
        tmp_path,
        f'# comment\nBOT_TOKEN="{TOKEN}"\nDATABASE_URL={DB}\nOWNER_IDS=1, 2,3\nLOG_LEVEL=debug\n',
    )
    assert settings.bot_token == TOKEN
    assert settings.owner_ids == frozenset({1, 2, 3})
    assert settings.log_level == "DEBUG"
    assert settings.telegram_proxy is None


def test_environment_overrides_file(tmp_path):
    settings = _load(
        tmp_path,
        f"BOT_TOKEN={TOKEN}\nDATABASE_URL={DB}\n",
        environ={"DATABASE_URL": "mysql+asyncmy://x:y@db:3306/other"},
    )
    assert settings.database_url.endswith("/other")


def test_empty_environment_variable_does_not_hide_file_value(tmp_path):
    settings = _load(
        tmp_path,
        f"BOT_TOKEN={TOKEN}\nDATABASE_URL={DB}\nTELEGRAM_PROXY=http://127.0.0.1:8080\n",
        environ={"TELEGRAM_PROXY": ""},
    )
    assert settings.telegram_proxy == "http://127.0.0.1:8080"


def test_missing_token_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, f"DATABASE_URL={DB}\n")


def test_token_not_required_for_migrations(tmp_path):
    settings = _load(tmp_path, f"DATABASE_URL={DB}\n", require_bot_token=False)
    assert settings.bot_token == ""


def test_malformed_token_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, f"BOT_TOKEN=not-a-token\nDATABASE_URL={DB}\n")


def test_missing_database_url_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, f"BOT_TOKEN={TOKEN}\n")


def test_invalid_owner_ids_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, f"BOT_TOKEN={TOKEN}\nDATABASE_URL={DB}\nOWNER_IDS=abc\n")


def test_invalid_log_level_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, f"BOT_TOKEN={TOKEN}\nDATABASE_URL={DB}\nLOG_LEVEL=loud\n")


def test_token_is_not_in_repr(tmp_path):
    settings = _load(tmp_path, f"BOT_TOKEN={TOKEN}\nDATABASE_URL={DB}\n")
    assert TOKEN not in repr(settings)
    assert "u:p@" not in repr(settings)


def test_sync_url_conversion():
    assert to_sync_url(DB).startswith("mysql+pymysql://u:p@")
    assert to_sync_url("sqlite+aiosqlite:///:memory:") == "sqlite:///:memory:"
    assert to_sync_url("postgresql://x") == "postgresql://x"


def test_parse_env_file_missing_file(tmp_path):
    assert parse_env_file(tmp_path / "nope.env") == {}
