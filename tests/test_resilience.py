"""تست منطق تلاش دوباره در برابر خطاهای گذرای شبکه."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import GetMe

from platforms.telegram.resilience import is_transient, with_retry


async def test_retries_transient_errors_until_success():
    calls: list[int] = []

    async def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise aiohttp.ServerDisconnectedError("server disconnected")
        return "ok"

    assert await with_retry(flaky, attempts=3, base_delay=0) == "ok"
    assert len(calls) == 3


async def test_gives_up_after_last_attempt():
    calls: list[int] = []

    async def always_fails() -> None:
        calls.append(1)
        raise aiohttp.ServerDisconnectedError("server disconnected")

    with pytest.raises(aiohttp.ServerDisconnectedError):
        await with_retry(always_fails, attempts=2, base_delay=0)
    assert len(calls) == 2


async def test_does_not_retry_non_transient_errors():
    calls: list[int] = []

    async def boom() -> None:
        calls.append(1)
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        await with_retry(boom, attempts=3, base_delay=0)
    assert len(calls) == 1


async def test_timeout_is_retried():
    calls: list[int] = []

    async def slow() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise asyncio.TimeoutError
        return "ok"

    assert await with_retry(slow, attempts=2, base_delay=0) == "ok"
    assert len(calls) == 2


async def test_rate_limit_is_retried():
    calls: list[int] = []

    async def limited() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise TelegramRetryAfter(method=GetMe(), message="Too Many Requests", retry_after=0)
        return "ok"

    assert await with_retry(limited, attempts=2, max_delay=0.1) == "ok"
    assert len(calls) == 2


def test_is_transient_classification():
    assert is_transient(aiohttp.ServerDisconnectedError("x"))
    assert is_transient(asyncio.TimeoutError())
    assert is_transient(TelegramRetryAfter(method=GetMe(), message="m", retry_after=1))
    assert not is_transient(ValueError("x"))
    assert not is_transient(TelegramBadRequest(method=GetMe(), message="bad"))
