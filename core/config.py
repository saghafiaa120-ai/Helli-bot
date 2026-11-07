"""تنظیمات برنامه.

مقادیر از فایل `.env` و متغیرهای محیطی خوانده می‌شوند (متغیر محیطی اولویت دارد).
هیچ توکن یا رمزی نباید در سورس کد نوشته شود.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$")
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(Exception):
    """خطای تنظیمات نامعتبر یا ناقص."""


def to_sync_url(url: str) -> str:
    """تبدیل آدرس دیتابیس ناهمگام به همگام (برای Alembic و پنل وب)."""
    replacements = (
        ("mysql+asyncmy://", "mysql+pymysql://"),
        ("mysql+aiomysql://", "mysql+pymysql://"),
        ("sqlite+aiosqlite://", "sqlite://"),
    )
    for old, new in replacements:
        if url.startswith(old):
            return new + url[len(old):]
    return url


class Settings(BaseModel):
    """تنظیمات اعتبارسنجی‌شده برنامه."""

    model_config = ConfigDict(frozen=True)

    bot_token: str = Field(default="", repr=False)
    database_url: str = Field(repr=False)
    owner_ids: frozenset[int] = frozenset()
    log_level: str = "INFO"
    telegram_proxy: str | None = None

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in _LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(_LOG_LEVELS)}")
        return level

    @property
    def sync_database_url(self) -> str:
        return to_sync_url(self.database_url)


def parse_env_file(path: Path) -> dict[str, str]:
    """خواندن یک فایل `.env` ساده (KEY=VALUE). کامنت داخل خط پشتیبانی نمی‌شود."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    # utf-8-sig: ویرایشگرهای ویندوز (مثل Notepad) گاهی BOM به ابتدای فایل اضافه می‌کنند.
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _parse_owner_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise ConfigError(f"OWNER_IDS باید فهرست عددی جداشده با کاما باشد، نه «{part}»") from exc
    return frozenset(ids)


def load_settings(
    env_file: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    require_bot_token: bool = True,
) -> Settings:
    """بارگذاری تنظیمات.

    `environ` برای تست قابل جایگزینی است. `require_bot_token=False` برای ابزارهایی
    مثل Alembic است که به توکن نیاز ندارند.
    """
    path = Path(env_file) if env_file is not None else PROJECT_ROOT / ".env"
    merged: dict[str, str] = dict(parse_env_file(path))
    for key, value in (os.environ if environ is None else environ).items():
        # متغیر محیطیِ خالی، مقدار فایل را بی‌اثر نمی‌کند.
        if value.strip() or key not in merged:
            merged[key] = value

    token = merged.get("BOT_TOKEN", "").strip()
    if require_bot_token:
        if not token:
            raise ConfigError("BOT_TOKEN تنظیم نشده است. آن را در فایل .env قرار دهید.")
        if not _TOKEN_RE.match(token):
            raise ConfigError("BOT_TOKEN فرمت معتبر ندارد (مثال: 123456:ABC...).")

    database_url = merged.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ConfigError("DATABASE_URL تنظیم نشده است.")

    try:
        return Settings(
            bot_token=token,
            database_url=database_url,
            owner_ids=_parse_owner_ids(merged.get("OWNER_IDS", "")),
            log_level=merged.get("LOG_LEVEL", "").strip() or "INFO",
            telegram_proxy=merged.get("TELEGRAM_PROXY", "").strip() or None,
        )
    except ValidationError as exc:
        raise ConfigError(f"تنظیمات نامعتبر: {exc}") from exc
