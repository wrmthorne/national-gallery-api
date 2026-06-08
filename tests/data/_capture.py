"""Capture one real `_source` document per entity type from the live API.

Run with `uv run python -m tests.data._capture` (needs network). Overwrites the
JSON files in this directory. These are genuine API documents used as test
inputs, so they are regenerated, never hand-edited. Re-run after an API change.
"""

import json
from pathlib import Path

from national_gallery_api import NationalGallery

HERE = Path(__file__).parent

# (filename stem, resource attribute, optional search text to find a rich doc)
TARGETS = [
    ("person", "people", "van gogh"),
    ("organisation", "organisations", None),
    ("work", "works", "sunflowers"),
    ("concept", "concepts", None),
    ("place", "places", None),
    ("event", "events", None),
    ("exhibition", "exhibitions", None),
    ("location", "locations", None),
    ("publication", "publications", None),
    ("archive", "archives", None),
    ("media", "media", None),
    ("package", "packages", None),
]


def main() -> None:
    with NationalGallery() as ng:
        for stem, attr, text in TARGETS:
            resource = getattr(ng, attr)
            results = resource.search(text) if text else resource.search()
            if not results:
                print(f"WARN  {stem}: no results")
                continue
            doc = results[0].raw
            (HERE / f"{stem}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False))
            print(f"ok    {stem}: {results[0].title!r}")


if __name__ == "__main__":
    main()
