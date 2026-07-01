# national-gallery-api

A small Python wrapper around the National Gallery (London) Elasticsearch
search endpoint (`https://data.ng.ac.uk/es/public/_search`).

It provides two things:

1. Pydantic models that mirror the API's records allowing for a more pythonic interface with the National Gallery API
2. Plain-text rendering of records e.g. for use in LLM prompts (entity disambiguation, authority linking, etc.)

The backend is schemaless, so the models are deliberately loose: they surface the common fields as typed attributes and keep the full original record on `.raw`.

## Setup

```
pip install "national-gallery-api[async]"
```

## Quick start

The following entities are available: `people`, `organisations`, `works`, `events`, `exhibitions`, `places`, `locations`, `concepts`, `publications`, `archives`, `media`, and `packages`.

### Search records

```python
from national_gallery_api import NationalGallery

with NationalGallery() as ng:
    results = ng.people.search("rembrandt", actual="Individual", size=5)

    for person in results:
        print(person.title, person.pid, person.dates)
```

### Look up a single record by PID

```python
with NationalGallery() as ng:
    vincent = ng.people.get("0QCE-0001-0000-0000")
    print(vincent.title)          # Vincent van Gogh
    print(vincent.external_ids)   # ULAN, Wikidata, RKD, VIAF, ...
```

## Paging over all results

`search` returns a single page. Use `iter_all` to lazily walk an entire result set:

```python
with NationalGallery() as ng:
    for person in ng.people.iter_all(actual="Individual", page_size=100):
        ...  # process one record at a time; pages are fetched as you go
```

## Caching

Caching is off by default. Enable it when running batch jobs that issue many repeated queries, so identical requests are served locally instead of hitting the API:

```python
with NationalGallery(cache=True, ttl=3600, database_path="hishel_cache.db") as ng:
    ...
```

## Async

`AsyncNationalGallery` mirrors the sync client. `search`, `get`, and raw queries are coroutines, and `iter_all` is an async generator:

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

`to_context` renders a single record, and `render_candidates` renders a set of records for disambiguation. Both are deterministic: field order and labels are fixed, multivalued fields are de-duplicated, and `render_candidates` orders candidates by PID regardless of input order, so the same input always produces the same string (useful for reproducible, cacheable prompts).

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

## Raw Elasticsearch queries

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