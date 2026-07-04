# National Gallery API Wrapper

A small Python wrapper around the National Gallery (London) Elasticsearch search endpoint (`https://data.ng.ac.uk/es/public/_search`). The library aims to provide:

1. A more pythonic interface with the National Gallery API
2. Plain-text rendering of records e.g. for use in LLM prompts (entity disambiguation, authority linking, etc.)

> National Gallery data is offered for reuse under specific [licences](https://www.nationalgallery.org.uk/documentation/ngacuk/licences).

## Setup

```bash
# sync only
pip install national-gallery-api

# sync and async
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

## Iterate over all results

`iter_all` lazily walks an entire result set, handling paging internally:

```python
with NationalGallery() as ng:
    for person in ng.people.iter_all(actual="Individual", page_size=100):
        ...
```

## Caching

Caching is disabled by default. To minimise server load when making frequent repeat requests (e.g. during batch jobs), cache should be enabled:

```python
with NationalGallery(cache=True, ttl=3600, database_path="hishel_cache.db") as ng:
    ...
```

## Async

`AsyncNationalGallery` mirrors the sync client.

```python
import asyncio
from national_gallery_api import AsyncNationalGallery

async def main():
    async with AsyncNationalGallery() as ng:
        results = await ng.works.search("portrait", size=5)
        for work in results:
            ...

        async for work in ng.works.iter_all("portrait", page_size=50):
            ...

asyncio.run(main())
```

## Rendering for LLM context

```python
from national_gallery_api import NationalGallery, to_context, render_candidates

with NationalGallery() as ng:
    vincent = ng.people.get("0QCE-0001-0000-0000")
    print(to_context(vincent)) # for single entities

    candidates = ng.people.search("rembrandt", actual="Individual", size=5)
    print(render_candidates(candidates)) # for record sets
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

## Free-text search across all types

Calling `search` on the client object with a string performs a free-text search across all fields:

```python
with NationalGallery() as ng:
    results = ng.search("van gogh", size=10)
    for entity in results:
        ...
    
    # mixed collections of entity types can still be passed
    print(render_candidates(results))
```

## Raw Elasticsearch queries

Calling `search` on the client object with an Elasticsearch body allows for custom queries, returning an unparsed response dict. This should be used for any queries or fields not handled by the typed API:

```python
with NationalGallery() as ng:
    payload = ng.search({"query": {"match_all": {}}, "size": 0})
    print(payload["hits"]["total"])
```

Query bodies can also be built with the `build_search` helper:

```python
from national_gallery_api import build_search, EntityType

body = build_search("van gogh", base=EntityType.AGENT, actual="Individual", size=10)
```