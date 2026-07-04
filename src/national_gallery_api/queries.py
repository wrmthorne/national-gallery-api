from enum import StrEnum
from typing import Any


class EntityType(StrEnum):
    AGENT = "agent"
    OBJECT = "object"
    EVENT = "event"
    EXHIBITION = "exhibition"
    PLACE = "place"
    LOCATION = "location"
    CONCEPT = "concept"
    PUBLICATION = "publication"
    ARCHIVE = "archive"
    MEDIA = "media"
    PACKAGE = "package"


def build_search(
    text: str | None = None,
    *,
    base: EntityType | str | None = None,
    actual: str | None = None,
    size: int = 10,
    from_: int = 0,
) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    if text:
        must.append({"match": {"summary.title": text}})
    if base is not None:
        must.append({"term": {"@datatype.base": str(base)}})
    if actual is not None:
        must.append({"term": {"@datatype.actual": actual}})
    query: dict[str, Any] = {"bool": {"must": must}} if must else {"match_all": {}}
    return {"query": query, "size": size, "from": from_}


def build_free_text(text: str, *, size: int = 10, from_: int = 0) -> dict[str, Any]:
    """Build a free-text query matching across all fields and every entity type.

    Unlike :func:`build_search`, this applies no ``@datatype`` filter, so results may be of any and of mixed
    types. ``multi_match`` over ``["*"]`` tolerates arbitrary user input (special characters and Lucene operators
    that would make ``query_string`` fail).
    """
    return {"query": {"multi_match": {"query": text, "fields": ["*"]}}, "size": size, "from": from_}
