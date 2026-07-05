from collections.abc import Callable, Iterable

from .models import (
    Archive,
    Concept,
    Entity,
    Event,
    Exhibition,
    Location,
    Media,
    Node,
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


# --- extraction helpers -------------------------------------------------------------------------
# Each spec entry is a guard-free navigation one-liner. Navigation *within* a present field is lenient (a
# missing sub-path yields an empty Node / None / []); an absent top-level key on the entity raises, which
# `to_context` catches per-extractor and renders as an omitted field.


def _first(node: Node) -> Node:
    """First item of a single-or-list field (an empty Node if absent)."""
    return next(iter(node), Node(None))


def _titles(node: Node) -> list[str]:
    """Titles of a list of references/entities (skipping any without one)."""
    return [t for r in node.refs() if (t := r.title)]


def _name(node: Node) -> str | None:
    """The ``name`` value of the first item of a ``Named`` field (``publisher``/``place``/``repository``)."""
    values = _first(node).name.values
    return values[0] if values else None


def _identifier(entity: Entity, type_: str) -> str | None:
    return next((i.value for i in entity.identifier if i.type == type_), None)


def _description(entity: Entity, type_: str) -> str | None:
    """The plain-text ``value`` of the description of a given ``type`` (not the HTML ``formatted``)."""
    return next((d.value for d in entity.description if d.type == type_), None)


def _coordinate(entity: Entity) -> str | None:
    c = _first(entity.coordinates)
    try:
        return f"{float(c.latitude.value)}, {float(c.longitude.value)}"
    except (TypeError, ValueError):
        return None


def _location(entity: Entity) -> str:
    return ", ".join(v for v in [entity.address.city.value, entity.address.country.value] if v)


# --- per-type summary specs ---------------------------------------------------------------------
# Each entry is (label, extractor). The extractor returns a str, a list, a Node, or None; `_fmt` normalises.

Extractor = Callable[[Entity], object]

_SPECS: dict[type[Entity], list[tuple[str, Extractor]]] = {
    Person: [
        ("Names", lambda e: e.name.values),
        ("Dates", lambda e: e.date[0].value),
        ("Roles", lambda e: sorted(r.value for r in e.role)),
        ("External IDs", lambda e: sorted(e.external_ids)),
    ],
    Organisation: [
        ("Names", lambda e: e.name.values),
        ("Location", _location),
        ("Websites", lambda e: e.web.url.values),
    ],
    Work: [
        ("Object number", lambda e: _identifier(e, "object number")),
        ("Makers", lambda e: _titles(e.creation[0].maker)),
        ("Date", lambda e: e.creation[0].date[0].value),
        ("Description", lambda e: _description(e, "short text")),
    ],
    Event: [
        ("Dates", lambda e: e.date[0].value),
        ("Names", lambda e: e.name.values),
    ],
    Exhibition: [
        ("Dates", lambda e: e.date[0].value),
        ("Venues", lambda e: _titles(e.venue)),
    ],
    Place: [
        ("Coordinates", _coordinate),
        ("Within", lambda e: e.parent),
    ],
    Location: [
        ("Floor", lambda e: e.floor.value),
    ],
    Concept: [
        ("Terms", lambda e: e.term.values),
        ("Broader", lambda e: e.parent),
    ],
    Publication: [
        ("Authors", lambda e: _titles(e.work.creation.maker)),
        ("Date", lambda e: e.creation[0].date[0].value),
        ("Publisher", lambda e: _name(e.creation[0].publisher)),
        ("Place", lambda e: _name(e.creation[0].place)),
    ],
    Archive: [
        ("Level", lambda e: e.level.value),
        ("Date", lambda e: e.creation.date[0].value),
        ("Repository", lambda e: e.repository),
        ("Within", lambda e: e.parent),
    ],
    Media: [
        ("Type", lambda e: e.source.type),
        ("URL", lambda e: e.source.location.value),
    ],
    Package: [
        ("Objects", lambda e: _titles(e.object)),
    ],
}

# Fallback for the base Entity and any type without a spec (e.g. mixed free-text results): the fields common
# to almost every NG document.
_GENERIC: list[tuple[str, Extractor]] = [
    ("Type", lambda e: e.actual or e.base),
    ("Names", lambda e: e.name.values),
    ("Dates", lambda e: e.date[0].value),
]


def _truncate(text: str, limit: int | None) -> str:
    if limit is None or len(text) <= limit:
        return text
    return f"{text[:limit]}…(+{len(text) - limit} chars)"


def _fmt(value: object, max_chars: int | None) -> str | None:
    """Normalise an extractor result to a display string (capped at ``max_chars``), or None when empty."""
    if isinstance(value, Node):
        value = value.raw
    if value is None:
        return None
    text = _join(str(v) for v in value if v) if isinstance(value, (list, tuple)) else str(value).strip()
    return _truncate(text, max_chars) if text else None


def _extract(extract: Extractor, entity: Entity) -> object:
    """Run an extractor, treating an absent top-level key (raised by the entity) as an empty field."""
    try:
        return extract(entity)
    except AttributeError:
        return None


def to_context(entity: Entity, *, max_chars: int | None = 200) -> str:
    """A compact, distinguishing summary of an entity for disambiguation.

    The per-type field list comes from :data:`_SPECS` (falling back to :data:`_GENERIC` for unspecified or
    mixed types); the model itself stays schema-free, and each spec entry is a guard-free navigation one-liner.

    Long field values are truncated to ``max_chars`` with a ``…(+N chars)`` tail; pass ``max_chars=None`` for
    the full, untruncated text.
    """
    header = f"{type(entity).__name__}: {entity.title or '(unknown)'}"
    fields = [_field("PID", entity.pid)]
    fields += [
        _field(label, _fmt(_extract(extract, entity), max_chars))
        for label, extract in _SPECS.get(type(entity), _GENERIC)
    ]
    return _block(header, fields)


def render_candidates(entities: Iterable[Entity], *, max_chars: int | None = 200) -> str:
    unique = {e.pid: e for e in entities if e.pid is not None}
    ordered = [unique[pid] for pid in sorted(unique)]
    if not ordered:
        return "No candidates."
    return "\n\n".join(f"Candidate {i}:\n{to_context(e, max_chars=max_chars)}" for i, e in enumerate(ordered, 1))
