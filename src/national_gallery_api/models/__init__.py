from typing import Any

from .agent import Address, Agent, Organisation, Person, Web
from .base import DataType, Entity, Identifier, Named, Reference, ValueEntry
from .collection import Location, Package
from .concept import Concept, Coordinate, Place, Term
from .event import Event, Exhibition, Status
from .material import Archive, Media, MediaSource, Publication
from .work import BibliographyEntry, Creation, Maker, Work

_BY_BASE: dict[str, type[Entity]] = {
    "object": Work,
    "event": Event,
    "exhibition": Exhibition,
    "place": Place,
    "location": Location,
    "concept": Concept,
    "publication": Publication,
    "archive": Archive,
    "media": Media,
    "package": Package,
}


def model_for(source: dict[str, Any]) -> type[Entity]:
    datatype = source.get("@datatype") or {}
    base = datatype.get("base")
    if base == "agent":
        return Organisation if datatype.get("actual") == "Organisation" else Person
    return _BY_BASE.get(base, Entity)


def parse_hit(hit: dict[str, Any]) -> Entity:
    source = hit.get("_source", hit)
    return model_for(source).from_hit(hit)


def parse_response(payload: dict[str, Any]) -> list[Entity]:
    hits = payload.get("hits", {}).get("hits", [])
    return [parse_hit(hit) for hit in hits]


__all__ = [
    "Address", "Agent", "Archive", "BibliographyEntry", "Concept", "Coordinate",
    "Creation", "DataType", "Entity", "Event", "Exhibition", "Identifier",
    "Location", "Maker", "Media", "MediaSource", "Named", "Organisation",
    "Package", "Person", "Place", "Publication", "Reference", "Status", "Term",
    "ValueEntry", "Web", "Work", "model_for", "parse_hit", "parse_response",
]
