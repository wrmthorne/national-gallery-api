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
