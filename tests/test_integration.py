import pytest

from national_gallery_api import AsyncNationalGallery, NationalGallery, Person, Work


@pytest.mark.vcr
def test_search_people_returns_real_results():
    with NationalGallery() as ng:
        results = ng.people.search("van gogh")
    assert len(results) > 0
    assert all(isinstance(r, Person) for r in results)
    assert results.total.value > 0
    assert any("Gogh" in (r.title or "") for r in results)


@pytest.mark.vcr
def test_get_work_by_pid():
    with NationalGallery() as ng:
        results = ng.works.search("sunflowers")
    assert len(results) > 0
    work = results[0]
    assert isinstance(work, Work)
    assert work.pid

    with NationalGallery() as ng:
        fetched = ng.works.get(work.pid)
    assert fetched.pid == work.pid


@pytest.mark.vcr
def test_iter_all_pages_real_data():
    # No text filter, so this pages over the whole works collection; we break
    # after a few pages. search_after ordering (by @admin.uid) is deterministic,
    # so the cassette replays the same pages every run.
    with NationalGallery() as ng:
        items = []
        for work in ng.works.iter_all(page_size=10):
            items.append(work)
            if len(items) >= 25:  # span more than one page, then stop
                break
    assert len(items) >= 11  # proves a second page was fetched and parsed
    assert all(isinstance(w, Work) for w in items)


@pytest.mark.vcr
async def test_async_search_people():
    async with AsyncNationalGallery() as ng:
        results = await ng.people.search("rembrandt")
    assert len(results) > 0
    assert all(isinstance(r, Person) for r in results)
