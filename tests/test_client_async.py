import httpx
import pytest

from national_gallery_api import AsyncNationalGallery, Person, Work
from national_gallery_api.exceptions import APIError, NotFoundError

from .conftest import PERSON_SOURCE, WORK_SOURCE, MockAPI, es_payload, identifier_of, pid_of


def reply(api: MockAPI, payload: dict) -> None:
    api.respond = lambda _body: httpx.Response(200, json=payload)


async def test_async_search_returns_typed_results(mock_api: MockAPI):
    reply(mock_api, es_payload([PERSON_SOURCE], total=1))
    async with AsyncNationalGallery() as ng:
        results = await ng.people.search("van gogh")
    assert isinstance(results[0], Person)
    assert results.total.value == 1
    assert results[0].title == PERSON_SOURCE["summary"]["title"]


async def test_async_search_applies_default_actual(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    async with AsyncNationalGallery() as ng:
        await ng.people.search("x")
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"@datatype.actual": "Individual"}} in must


async def test_async_get_returns_record(mock_api: MockAPI):
    reply(mock_api, es_payload([PERSON_SOURCE]))
    async with AsyncNationalGallery() as ng:
        person = await ng.people.get(pid_of(PERSON_SOURCE))
    assert person.title == PERSON_SOURCE["summary"]["title"]


async def test_async_get_raises_not_found(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    async with AsyncNationalGallery() as ng:
        with pytest.raises(NotFoundError):
            await ng.people.get("missing")


async def test_async_get_by_ng_number(mock_api: MockAPI):
    reply(mock_api, es_payload([WORK_SOURCE]))
    ng_number = identifier_of(WORK_SOURCE, "object number")
    async with AsyncNationalGallery() as ng:
        work = await ng.works.get_by_ng_number(ng_number)
    assert isinstance(work, Work)
    assert work.object_number == ng_number
    assert mock_api.last_request["query"] == {"term": {"identifier.value": ng_number}}


async def test_async_get_by_ng_number_raises_not_found(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    async with AsyncNationalGallery() as ng:
        with pytest.raises(NotFoundError):
            await ng.works.get_by_ng_number("NG0000")


async def test_async_raw_search(mock_api: MockAPI):
    reply(mock_api, es_payload([], total=7))
    async with AsyncNationalGallery() as ng:
        payload = await ng.search({"query": {"match_all": {}}})
    assert payload["hits"]["total"]["value"] == 7


async def test_async_api_error(mock_api: MockAPI):
    mock_api.respond = lambda _body: httpx.Response(503, text="unavailable")
    async with AsyncNationalGallery() as ng:
        with pytest.raises(APIError) as exc:
            await ng.search({"query": {}})
    assert exc.value.status_code == 503


async def test_async_iter_all_pages(mock_api: MockAPI):
    page1 = es_payload([WORK_SOURCE, WORK_SOURCE], sorts=[["a"], ["b"]])
    page2 = es_payload([WORK_SOURCE], sorts=[["c"]])
    mock_api.reply_once_with([page1, page2])

    async with AsyncNationalGallery() as ng:
        items = [w async for w in ng.works.iter_all(page_size=2)]

    assert len(items) == 3
    assert all(isinstance(w, Work) for w in items)
    assert mock_api.requests[1]["search_after"] == ["b"]


async def test_async_iter_all_empty(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    async with AsyncNationalGallery() as ng:
        items = [p async for p in ng.people.iter_all()]
    assert items == []
