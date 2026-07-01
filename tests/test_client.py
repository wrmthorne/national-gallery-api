import httpx
import pytest

from national_gallery_api import NationalGallery, Person, Work
from national_gallery_api.exceptions import APIError, NotFoundError

from .conftest import PERSON_SOURCE, WORK_SOURCE, MockAPI, es_payload, identifier_of, pid_of


def reply(api: MockAPI, payload: dict) -> None:
    api.respond = lambda _body: httpx.Response(200, json=payload)


def test_search_returns_typed_results(mock_api: MockAPI):
    reply(mock_api, es_payload([PERSON_SOURCE]))
    with NationalGallery() as ng:
        results = ng.people.search("van gogh")
    assert len(results) == 1
    assert isinstance(results[0], Person)
    assert results[0].title == PERSON_SOURCE["summary"]["title"]
    # __iter__ yields the same typed records.
    assert next(iter(results)).pid == pid_of(PERSON_SOURCE)


def test_search_results_total_exact(mock_api: MockAPI):
    reply(mock_api, es_payload([PERSON_SOURCE], total=1, relation="eq"))
    with NationalGallery() as ng:
        results = ng.people.search()
    assert results.total.value == 1
    assert results.total.exact is True


def test_search_results_total_capped(mock_api: MockAPI):
    reply(mock_api, es_payload([PERSON_SOURCE], total=10000, relation="gte"))
    with NationalGallery() as ng:
        results = ng.people.search()
    assert results.total.value == 10000
    assert results.total.exact is False


def test_search_results_aggregations(mock_api: MockAPI):
    reply(mock_api, es_payload([], aggregations={"by_type": {"buckets": []}}))
    with NationalGallery() as ng:
        results = ng.works.search()
    assert results.aggregations == {"by_type": {"buckets": []}}
    assert results.raw["hits"]["total"]["value"] == 0


def test_missing_total_defaults_to_zero(mock_api: MockAPI):
    reply(mock_api, {"hits": {"hits": []}})
    with NationalGallery() as ng:
        results = ng.people.search()
    assert results.total.value == 0
    assert results.total.relation == "eq"


def test_people_resource_applies_default_actual(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        ng.people.search("rembrandt")
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"@datatype.base": "agent"}} in must
    assert {"term": {"@datatype.actual": "Individual"}} in must


def test_actual_can_be_overridden(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        ng.people.search("x", actual="Group")
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"@datatype.actual": "Group"}} in must


def test_actual_none_drops_the_clause(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        ng.people.search("x", actual=None)
    must = mock_api.last_request["query"]["bool"]["must"]
    assert all("@datatype.actual" not in c.get("term", {}) for c in must)


def test_works_resource_has_no_default_actual(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        ng.works.search("sunflowers")
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"@datatype.base": "object"}} in must
    assert all("@datatype.actual" not in c.get("term", {}) for c in must)


def test_search_passes_size_and_from(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        ng.works.search("x", size=5, from_=10)
    assert mock_api.last_request["size"] == 5
    assert mock_api.last_request["from"] == 10


def test_get_returns_single_record(mock_api: MockAPI):
    reply(mock_api, es_payload([PERSON_SOURCE]))
    pid = pid_of(PERSON_SOURCE)
    with NationalGallery() as ng:
        person = ng.people.get(pid)
    assert person.title == PERSON_SOURCE["summary"]["title"]
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"identifier.value": pid}} in must
    assert {"term": {"@datatype.base": "agent"}} in must


def test_get_raises_not_found_when_empty(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng, pytest.raises(NotFoundError):
        ng.people.get("does-not-exist")


def test_get_by_ng_number_returns_work(mock_api: MockAPI):
    reply(mock_api, es_payload([WORK_SOURCE]))
    ng_number = identifier_of(WORK_SOURCE, "object number")
    with NationalGallery() as ng:
        work = ng.works.get_by_ng_number(ng_number)
    assert isinstance(work, Work)
    assert work.object_number == ng_number
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"identifier.value": ng_number}} in must
    assert {"term": {"@datatype.base": "object"}} in must


def test_get_by_ng_number_normalises_input(mock_api: MockAPI):
    reply(mock_api, es_payload([WORK_SOURCE]))
    with NationalGallery() as ng:
        ng.works.get_by_ng_number("ng 3863")
    must = mock_api.last_request["query"]["bool"]["must"]
    assert {"term": {"identifier.value": "NG3863"}} in must


def test_get_by_ng_number_raises_not_found(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng, pytest.raises(NotFoundError):
        ng.works.get_by_ng_number("NG0000")


def test_raw_search_returns_payload(mock_api: MockAPI):
    reply(mock_api, es_payload([], total=42))
    with NationalGallery() as ng:
        payload = ng.search({"query": {"match_all": {}}, "size": 0})
    assert payload["hits"]["total"]["value"] == 42


def test_api_error_on_4xx(mock_api: MockAPI):
    mock_api.respond = lambda _body: httpx.Response(400, text="bad request")
    with NationalGallery() as ng, pytest.raises(APIError) as exc:
        ng.search({"query": {}})
    assert exc.value.status_code == 400


def test_api_error_on_5xx(mock_api: MockAPI):
    mock_api.respond = lambda _body: httpx.Response(500, text="boom")
    with NationalGallery() as ng, pytest.raises(APIError) as exc:
        ng.people.search("x")
    assert exc.value.status_code == 500


def test_iter_all_pages_with_search_after(mock_api: MockAPI):
    page1 = es_payload([WORK_SOURCE, WORK_SOURCE], sorts=[["a"], ["b"]])
    page2 = es_payload([WORK_SOURCE], sorts=[["c"]])
    mock_api.reply_once_with([page1, page2])

    with NationalGallery() as ng:
        items = list(ng.works.iter_all(page_size=2))

    assert len(items) == 3
    assert all(isinstance(w, Work) for w in items)
    # First page has no search_after; second pages from the last sort of page 1.
    assert "search_after" not in mock_api.requests[0]
    assert mock_api.requests[1]["search_after"] == ["b"]


def test_iter_all_stops_on_short_page(mock_api: MockAPI):
    # A page smaller than page_size means there is nothing more to fetch.
    reply(mock_api, es_payload([WORK_SOURCE], sorts=[["a"]]))
    with NationalGallery() as ng:
        items = list(ng.works.iter_all(page_size=10))
    assert len(items) == 1
    assert len(mock_api.requests) == 1


def test_iter_all_stops_when_sort_missing(mock_api: MockAPI):
    # A full page whose last hit lacks `sort` cannot be paged past.
    full_page = es_payload([WORK_SOURCE, WORK_SOURCE])  # no sorts
    mock_api.reply_once_with([full_page])
    with NationalGallery() as ng:
        items = list(ng.works.iter_all(page_size=2))
    assert len(items) == 2
    assert len(mock_api.requests) == 1


def test_iter_all_empty(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        assert list(ng.people.iter_all()) == []


def test_iter_all_sets_sort_in_body(mock_api: MockAPI):
    reply(mock_api, es_payload([]))
    with NationalGallery() as ng:
        list(ng.people.iter_all())
    assert mock_api.last_request["sort"] == [{"@admin.uid": "asc"}]
