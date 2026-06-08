from dataclasses import dataclass, field

import pytest
from hishel.httpx import AsyncCacheTransport, SyncCacheTransport
from httpx_retries import RetryTransport

from national_gallery_api.transport import (
    _NO_CACHE_DIRECTIVES,
    _RETRY_STATUS,
    _Cacheable,
    _retry,
    build_async_transport,
    build_sync_transport,
)


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)


def test_cacheable_accepts_plain_2xx():
    assert _Cacheable().apply(FakeResponse(200), None) is True
    assert _Cacheable().apply(FakeResponse(204), None) is True


def test_cacheable_rejects_non_2xx():
    for status in (199, 300, 404, 500):
        assert _Cacheable().apply(FakeResponse(status), None) is False


def test_cacheable_rejects_no_store_directives():
    for directive in _NO_CACHE_DIRECTIVES:
        resp = FakeResponse(200, {"cache-control": f"max-age=60, {directive}"})
        assert _Cacheable().apply(resp, None) is False


def test_cacheable_is_case_insensitive():
    resp = FakeResponse(200, {"cache-control": "No-Store"})
    assert _Cacheable().apply(resp, None) is False


def test_cacheable_allows_ordinary_cache_control():
    resp = FakeResponse(200, {"cache-control": "max-age=3600"})
    assert _Cacheable().apply(resp, None) is True


def test_cacheable_does_not_need_body():
    assert _Cacheable().needs_body() is False


def test_retry_config():
    retry = _retry()
    assert retry.total == 3
    assert set(retry.status_forcelist) == set(_RETRY_STATUS)


def test_build_sync_transport_without_cache_is_retry_only():
    transport = build_sync_transport(cache=False)
    assert isinstance(transport, RetryTransport)


def test_build_sync_transport_with_cache(tmp_path):
    transport = build_sync_transport(cache=True, database_path=str(tmp_path / "c.db"))
    assert isinstance(transport, SyncCacheTransport)


def test_build_async_transport_without_cache_is_retry_only():
    transport = build_async_transport(cache=False)
    assert isinstance(transport, RetryTransport)


def test_build_async_transport_with_cache(tmp_path):
    # The async SQLite cache backend ships in the optional `hishel[async]` extra.
    pytest.importorskip("anysqlite")
    transport = build_async_transport(cache=True, database_path=str(tmp_path / "c.db"))
    assert isinstance(transport, AsyncCacheTransport)
