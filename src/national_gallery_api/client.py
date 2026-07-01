from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
from pydantic import BaseModel

from .exceptions import APIError, NotFoundError
from .models import (
    Archive,
    Concept,
    Entity,
    Event,
    Exhibition,
    Location,
    Media,
    Organisation,
    Package,
    Person,
    Place,
    Publication,
    Work,
)
from .queries import EntityType, build_search
from .transport import build_async_transport, build_sync_transport

URL = "https://data.ng.ac.uk/es/public/_search"
_SORT = [{"@admin.uid": "asc"}]

# (attribute, model, base, default_actual)
_RESOURCES = [
    ("people", Person, EntityType.AGENT, "Individual"),
    ("organisations", Organisation, EntityType.AGENT, "Organisation"),
    ("works", Work, EntityType.OBJECT, None),
    ("events", Event, EntityType.EVENT, None),
    ("exhibitions", Exhibition, EntityType.EXHIBITION, None),
    ("places", Place, EntityType.PLACE, None),
    ("locations", Location, EntityType.LOCATION, None),
    ("concepts", Concept, EntityType.CONCEPT, None),
    ("publications", Publication, EntityType.PUBLICATION, None),
    ("archives", Archive, EntityType.ARCHIVE, None),
    ("media", Media, EntityType.MEDIA, None),
    ("packages", Package, EntityType.PACKAGE, None),
]


class Total(BaseModel):
    value: int = 0
    relation: str = "eq"

    @property
    def exact(self) -> bool:
        return self.relation == "eq"


class SearchResults[E: Entity]:
    def __init__(self, items: list[E], payload: dict[str, Any]) -> None:
        self._items = items
        self.raw = payload
        hits = payload.get("hits", {})
        self.total = Total.model_validate(hits.get("total") or {})
        self.aggregations: dict[str, Any] = payload.get("aggregations", {})

    def __iter__(self) -> Iterator[E]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> E:
        return self._items[index]


def _page_body(
    text: str | None, base: EntityType, actual: str | None, page_size: int, after: list[Any] | None
) -> dict[str, Any]:
    body = build_search(text, base=base, actual=actual, size=page_size, from_=0)
    body["sort"] = _SORT
    if after is not None:
        body["search_after"] = after
    return body


_UNSET: Any = object()


def _normalise_ng_number(ng_number: str) -> str:
    """Canonicalise a user-supplied NG number to the stored form (e.g. ``"ng 3863"`` -> ``"NG3863"``)."""
    return ng_number.replace(" ", "").upper()


def _resolve_actual(actual: str | None, default: str | None) -> str | None:
    return default if actual is _UNSET else actual


def _term_body(field: str, value: str, base: EntityType | None = None) -> dict[str, Any]:
    must: list[dict[str, Any]] = [{"term": {field: value}}]
    if base is not None:
        must.append({"term": {"@datatype.base": str(base)}})
    return {"query": {"bool": {"must": must}}, "size": 1}


def _one_or_raise[E: Entity](items: list[E], message: str) -> E:
    if not items:
        raise NotFoundError(message)
    return items[0]


def _next_after(hits: list[dict[str, Any]], page_size: int) -> list[Any] | None:
    """The ``search_after`` cursor for the next page, or ``None`` when paging should stop."""
    if not hits or len(hits) < page_size:
        return None
    return hits[-1].get("sort")


class _SyncResource[E: Entity]:
    def __init__(
        self, client: NationalGallery, model: type[E], base: EntityType, default_actual: str | None = None
    ) -> None:
        self._client = client
        self._model = model
        self._base = base
        self._default_actual = default_actual

    def search(
        self, text: str | None = None, *, actual: str | None = _UNSET, size: int = 10, from_: int = 0
    ) -> SearchResults[E]:
        actual = _resolve_actual(actual, self._default_actual)
        body = build_search(text, base=self._base, actual=actual, size=size, from_=from_)
        payload = self._client.search(body)
        return SearchResults(self._model.from_response(payload), payload)

    def get(self, pid: str) -> E:
        payload = self._client.search(_term_body("identifier.value", pid, self._base))
        return _one_or_raise(self._model.from_response(payload), f"No entity with PID {pid!r}")

    def iter_all(self, text: str | None = None, *, actual: str | None = _UNSET, page_size: int = 100) -> Iterator[E]:
        actual = _resolve_actual(actual, self._default_actual)
        after: list[Any] | None = None
        while True:
            payload = self._client.search(_page_body(text, self._base, actual, page_size, after))
            hits = payload.get("hits", {}).get("hits", [])
            for hit in hits:
                yield self._model.from_hit(hit)
            after = _next_after(hits, page_size)
            if after is None:
                return


class _SyncWorks(_SyncResource[Work]):
    def get_by_ng_number(self, ng_number: str) -> Work:
        """Fetch the single work bearing the given NG (object) number, e.g. ``"NG3863"``.

        Raises :class:`NotFoundError` if no work has that number.
        """
        payload = self._client.search(_term_body("identifier.value", _normalise_ng_number(ng_number), self._base))
        return _one_or_raise(self._model.from_response(payload), f"No work with NG number {ng_number!r}")


class NationalGallery:
    people: _SyncResource[Person]
    organisations: _SyncResource[Organisation]
    works: _SyncWorks
    events: _SyncResource[Event]
    exhibitions: _SyncResource[Exhibition]
    places: _SyncResource[Place]
    locations: _SyncResource[Location]
    concepts: _SyncResource[Concept]
    publications: _SyncResource[Publication]
    archives: _SyncResource[Archive]
    media: _SyncResource[Media]
    packages: _SyncResource[Package]

    def __init__(
        self,
        *,
        cache: bool = False,
        ttl: float | None = 3600.0,
        database_path: str = "hishel_cache.db",
        timeout: float = 30.0,
    ) -> None:
        transport = build_sync_transport(cache=cache, ttl=ttl, database_path=database_path)
        self._client = httpx.Client(transport=transport, timeout=timeout)
        for attr, model, base, default_actual in _RESOURCES:
            setattr(self, attr, _SyncResource(self, model, base, default_actual))
        self.works = _SyncWorks(self, Work, EntityType.OBJECT)

    def search(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(URL, json=body)
        if response.status_code >= 400:
            raise APIError(f"search failed: {response.text[:200]}", status_code=response.status_code)
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NationalGallery:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class _AsyncResource[E: Entity]:
    def __init__(
        self, client: AsyncNationalGallery, model: type[E], base: EntityType, default_actual: str | None = None
    ) -> None:
        self._client = client
        self._model = model
        self._base = base
        self._default_actual = default_actual

    async def search(
        self, text: str | None = None, *, actual: str | None = _UNSET, size: int = 10, from_: int = 0
    ) -> SearchResults[E]:
        actual = _resolve_actual(actual, self._default_actual)
        body = build_search(text, base=self._base, actual=actual, size=size, from_=from_)
        payload = await self._client.search(body)
        return SearchResults(self._model.from_response(payload), payload)

    async def get(self, pid: str) -> E:
        payload = await self._client.search(_term_body("identifier.value", pid, self._base))
        return _one_or_raise(self._model.from_response(payload), f"No entity with PID {pid!r}")

    async def iter_all(
        self, text: str | None = None, *, actual: str | None = _UNSET, page_size: int = 100
    ) -> AsyncIterator[E]:
        actual = _resolve_actual(actual, self._default_actual)
        after: list[Any] | None = None
        while True:
            payload = await self._client.search(_page_body(text, self._base, actual, page_size, after))
            hits = payload.get("hits", {}).get("hits", [])
            for hit in hits:
                yield self._model.from_hit(hit)
            after = _next_after(hits, page_size)
            if after is None:
                return


class _AsyncWorks(_AsyncResource[Work]):
    async def get_by_ng_number(self, ng_number: str) -> Work:
        """Fetch the single work bearing the given NG (object) number, e.g. ``"NG3863"``.

        Raises :class:`NotFoundError` if no work has that number.
        """
        payload = await self._client.search(
            _term_body("identifier.value", _normalise_ng_number(ng_number), self._base)
        )
        return _one_or_raise(self._model.from_response(payload), f"No work with NG number {ng_number!r}")


class AsyncNationalGallery:
    people: _AsyncResource[Person]
    organisations: _AsyncResource[Organisation]
    works: _AsyncWorks
    events: _AsyncResource[Event]
    exhibitions: _AsyncResource[Exhibition]
    places: _AsyncResource[Place]
    locations: _AsyncResource[Location]
    concepts: _AsyncResource[Concept]
    publications: _AsyncResource[Publication]
    archives: _AsyncResource[Archive]
    media: _AsyncResource[Media]
    packages: _AsyncResource[Package]

    def __init__(
        self,
        *,
        cache: bool = False,
        ttl: float | None = 3600.0,
        database_path: str = "hishel_cache.db",
        timeout: float = 30.0,
    ) -> None:
        transport = build_async_transport(cache=cache, ttl=ttl, database_path=database_path)
        self._client = httpx.AsyncClient(transport=transport, timeout=timeout)
        for attr, model, base, default_actual in _RESOURCES:
            setattr(self, attr, _AsyncResource(self, model, base, default_actual))
        self.works = _AsyncWorks(self, Work, EntityType.OBJECT)

    async def search(self, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(URL, json=body)
        if response.status_code >= 400:
            raise APIError(f"search failed: {response.text[:200]}", status_code=response.status_code)
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncNationalGallery:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
