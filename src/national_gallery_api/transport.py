import hishel
import httpx
from hishel import BaseFilter, FilterPolicy, Response
from hishel.httpx import AsyncCacheTransport, SyncCacheTransport
from httpx_retries import Retry, RetryTransport

_RETRY_STATUS = (429, 502, 503, 504)
_NO_CACHE_DIRECTIVES = ("no-store", "no-cache", "private")
_DEFAULT_TTL = 86400.0  # 24 hours
_DEFAULT_RETRY_CNT = 3
_DEFAULT_RETRY_BACKOFF = 0.5


class _Cacheable(BaseFilter[Response]):
    """Cache successful responses unless the server forbids it."""

    def needs_body(self) -> bool:
        return False

    def apply(self, item: Response, body: bytes | None) -> bool:
        if not 200 <= item.status_code < 300:
            return False
        directives = item.headers.get("cache-control", "").lower()
        return not any(d in directives for d in _NO_CACHE_DIRECTIVES)


def _retry() -> Retry:
    return Retry(total=_DEFAULT_RETRY_CNT, backoff_factor=_DEFAULT_RETRY_BACKOFF, status_forcelist=list(_RETRY_STATUS))


def _policy() -> FilterPolicy:
    policy = FilterPolicy(response_filters=[_Cacheable()])
    policy.use_body_key = True
    return policy


def build_sync_transport(
    *, cache: bool = False, ttl: float | None = _DEFAULT_TTL, database_path: str = "hishel_cache.db"
) -> httpx.BaseTransport:
    retry = RetryTransport(transport=httpx.HTTPTransport(), retry=_retry())
    if not cache:
        return retry
    storage = hishel.SyncSqliteStorage(database_path=database_path, default_ttl=ttl)
    # pyrefly: ignore[bad-argument-type]  # hishel's try/except ImportError stub confuses the type
    return SyncCacheTransport(next_transport=retry, storage=storage, policy=_policy())


def build_async_transport(
    *, cache: bool = False, ttl: float | None = _DEFAULT_TTL, database_path: str = "hishel_cache.db"
) -> httpx.AsyncBaseTransport:
    retry = RetryTransport(transport=httpx.AsyncHTTPTransport(), retry=_retry())
    if not cache:
        return retry
    storage = hishel.AsyncSqliteStorage(database_path=database_path, default_ttl=ttl)
    # pyrefly: ignore[bad-argument-type]  # hishel's try/except ImportError stub confuses the type
    return AsyncCacheTransport(next_transport=retry, storage=storage, policy=_policy())
