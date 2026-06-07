# national-gallery-api

A small Python wrapper around the National Gallery (London) Elasticsearch
search endpoint (`https://data.ng.ac.uk/es/public/_search`).

It provides two things:

1. Pydantic models that mirror the API's records allowing for a more pythonic interface with the National Gallery API
2. Plain-text rendering of records e.g. for use in LLM prompts (entity disambiguation, authority linking, etc.)

The backend is schemaless, so the models are deliberately loose: they surface the common fields as typed attributes and keep the full original record on `.raw` as an escape hatch.

## Requirements

- Python 3.12 or newer
- `httpx`, `hishel`, `httpx-retries`, `pydantic`
- For async usage with caching enabled, install the async extra so the async SQLite cache backend is available:

```
pip install "national-gallery-api" "hishel[async]"
```

## Quick start

```python
from national_gallery_api import NationalGallery

with NationalGallery() as ng:
    results = ng.people.search("rembrandt", actual="Individual", size=5)

    print(results.total.value, "matches", "(exact)" if results.total.exact else "(capped)")
    for person in results:
        print(person.title, person.pid, person.dates)
```

`search` returns a `SearchResults` object. It iterates typed models and also exposes:

- `.total` - a `Total` with `.value` (int) and `.relation`. Elasticsearch caps counts at 10,000; when that happens `.relation` is `"gte"` and the helper `.total.exact` is `False`, so you can tell an exact count from a capped one.
- `.aggregations` - the raw aggregations dict, if the query requested any.
- `.raw` - the unparsed response payload.

### Works

```python
with NationalGallery() as ng:
    works = ng.works.search("sunflowers", size=3)
    for work in works:
        print(work.title, work.object_number, work.makers, work.date)
```

### Look up a single record by PID

```python
with NationalGallery() as ng:
    vincent = ng.people.get("0QCE-0001-0000-0000")
    print(vincent.title)          # Vincent van Gogh
    print(vincent.external_ids)   # ULAN, Wikidata, RKD, VIAF, ...
```

`get` raises `NotFoundError` if no record has that PID.

## Model fields

`Person` exposes `title`, `pid`, `names`, `dates`, `external_ids`, `datatype`, and `raw`. `Work` exposes `title`, `pid`, `object_number`, `makers`, `date`, and `raw`. The `pid` is derived from the record's identifier list (it is not a top-level field). Equality and hashing are by PID, so `set(results)` removes duplicate records.

## Paging over all results

`search` returns a single page. To walk an entire result set without managing offsets yourself, use `iter_all`, which yields records lazily and handles paging internally:

```python
with NationalGallery() as ng:
    for person in ng.people.iter_all(actual="Individual", page_size=100):
        ...  # process one record at a time; pages are fetched as you go
```

`iter_all` uses Elasticsearch `search_after` under the hood, so it is not subject to the 10,000-record limit that applies to offset-based (`from` plus `size`) paging.

## Caching

Caching is off by default. Enable it when running batch jobs that issue many repeated queries, so identical requests are served locally instead of hitting the API:

```python
with NationalGallery(cache=True, ttl=3600, database_path="hishel_cache.db") as ng:
    ...
```

- `ttl` sets how long (in seconds) a cached response is reused; pass `None` to keep entries until they are evicted.
- The cache stores only successful responses, and it will not store a response that the server marks as non-cacheable (`no-store`, `no-cache`, or `private`).
- Requests are retried with backoff on transient errors (429, 502, 503, 504).

## Async

`AsyncNationalGallery` mirrors the sync client. `search`, `get`, and the raw escape hatch are coroutines, and `iter_all` is an async generator:

```python
import asyncio
from national_gallery_api import AsyncNationalGallery

async def main():
    async with AsyncNationalGallery() as ng:
        results = await ng.works.search("portrait", size=5)
        for work in results:
            print(work.title)

        async for work in ng.works.iter_all("portrait", page_size=50):
            ...

asyncio.run(main())
```

## Rendering for LLM context

`to_context` renders a single record, and `render_candidates` renders a set of records for disambiguation. Both are deterministic: field order and labels are fixed, multi-valued fields are de-duplicated, and `render_candidates` orders candidates by PID regardless of input order, so the same input always produces the same string (useful for reproducible, cacheable prompts).

```python
from national_gallery_api import NationalGallery, to_context, render_candidates

with NationalGallery() as ng:
    vincent = ng.people.get("0QCE-0001-0000-0000")
    print(to_context(vincent))

    candidates = ng.people.search("rembrandt", actual="Individual", size=5)
    print(render_candidates(candidates))
```

Example `to_context` output:

```
Person: Vincent van Gogh
  PID: 0QCE-0001-0000-0000
  Subtype: Individual
  Dates: 1853 - 1890
  Names: Vincent van Gogh; Gogh, Vincent van
  External IDs: http://viaf.org/viaf/9854560; http://vocab.getty.edu/ulan/500115588; https://rkd.nl/artists/32439; https://www.wikidata.org/entity/Q5582
```

## Raw escape hatch

If a query or field is not covered by the typed API, send a raw Elasticsearch query body and get back the unparsed response dict:

```python
with NationalGallery() as ng:
    payload = ng.search({"query": {"match_all": {}}, "size": 0})
    print(payload["hits"]["total"])
```

You can build query bodies with the helper used internally, if useful:

```python
from national_gallery_api import build_search, EntityType

body = build_search("van gogh", base=EntityType.AGENT, actual="Individual", size=10)
```

## Errors

- `NationalGalleryError` - base class for all errors raised by this package.
- `APIError` - the API returned an error status; carries `.status_code`.
- `NotFoundError` - `get` found no record for the given PID.