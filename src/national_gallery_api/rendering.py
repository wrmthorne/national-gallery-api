from collections.abc import Iterable
from functools import singledispatch

from .models import (
    Archive,
    Concept,
    Entity,
    Event,
    Exhibition,
    Location,
    Media,
    Organisation,
    Package,
    Person,
    Place,
    Publication,
    Work,
)


def _field(label: str, value: str | None) -> str | None:
    return f"  {label}: {value}" if value else None


def _join(values: Iterable[str]) -> str | None:
    return "; ".join(dict.fromkeys(v for v in values if v)) or None


def _block(header: str, fields: list[str | None]) -> str:
    return "\n".join([header, *(f for f in fields if f)])


@singledispatch
def to_context(entity: Entity) -> str:
    return _block(
        f"Entity: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Type", entity.datatype.base if entity.datatype else None)],
    )


@to_context.register
def _(entity: Person) -> str:
    subtype = entity.datatype.actual if entity.datatype else None
    return _block(
        f"Person: {entity.title or '(unknown)'}",
        [
            _field("PID", entity.pid),
            _field("Subtype", subtype),
            _field("Dates", entity.dates),
            _field("Names", _join(entity.names)),
            _field("External IDs", "; ".join(sorted(set(entity.external_ids))) or None),
        ],
    )


@to_context.register
def _(entity: Organisation) -> str:
    location = ", ".join(p for p in [entity.address.city, entity.address.country] if p) if entity.address else None
    return _block(
        f"Organisation: {entity.title or '(unknown)'}",
        [
            _field("PID", entity.pid),
            _field("Names", _join(entity.names)),
            _field("Location", location),
            _field("Websites", _join(entity.websites)),
        ],
    )


@to_context.register
def _(entity: Work) -> str:
    return _block(
        f"Work: {entity.title or '(unknown)'}",
        [
            _field("PID", entity.pid),
            _field("Object number", entity.object_number),
            _field("Makers", _join(entity.makers)),
            _field("Date", entity.date),
            _field("Bibliography", _join(b.title for b in entity.bibliography if b.title)),
        ],
    )


@to_context.register
def _(entity: Event) -> str:
    return _block(
        f"Event: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Dates", entity.dates)],
    )


@to_context.register
def _(entity: Exhibition) -> str:
    return _block(
        f"Exhibition: {entity.title or '(unknown)'}",
        [
            _field("PID", entity.pid),
            _field("Dates", entity.dates),
            _field("Venues", _join(v.title for v in entity.venues if v.title)),
        ],
    )


@to_context.register
def _(entity: Place) -> str:
    coord = ", ".join(str(c) for c in entity.coordinate) if entity.coordinate else None
    return _block(
        f"Place: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Coordinates", coord), _field("Within", entity.parent)],
    )


@to_context.register
def _(entity: Location) -> str:
    return _block(
        f"Location: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Floor", str(entity.floor) if entity.floor is not None else None)],
    )


@to_context.register
def _(entity: Concept) -> str:
    return _block(
        f"Concept: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Terms", _join(entity.terms)), _field("Broader", entity.parent)],
    )


@to_context.register
def _(entity: Publication) -> str:
    return _block(
        f"Publication: {entity.title or '(unknown)'}",
        [
            _field("PID", entity.pid),
            _field("Authors", _join(entity.authors)),
            _field("Date", entity.date),
            _field("Publisher", entity.publisher),
            _field("Place", entity.place_of_publication),
        ],
    )


@to_context.register
def _(entity: Archive) -> str:
    return _block(
        f"Archive: {entity.title or '(unknown)'}",
        [
            _field("PID", entity.pid),
            _field("Level", entity.level_value),
            _field("Date", entity.date),
            _field("Repository", entity.repository),
            _field("Within", entity.parent),
        ],
    )


@to_context.register
def _(entity: Media) -> str:
    return _block(
        f"Media: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Type", entity.media_type), _field("URL", entity.url)],
    )


@to_context.register
def _(entity: Package) -> str:
    return _block(
        f"Package: {entity.title or '(unknown)'}",
        [_field("PID", entity.pid), _field("Objects", _join(entity.object_titles))],
    )


def render_candidates(entities: Iterable[Entity]) -> str:
    unique = {e.pid: e for e in entities if e.pid is not None}
    ordered = [unique[pid] for pid in sorted(unique)]
    if not ordered:
        return "No candidates."
    return "\n\n".join(f"Candidate {i}:\n{to_context(e)}" for i, e in enumerate(ordered, 1))
