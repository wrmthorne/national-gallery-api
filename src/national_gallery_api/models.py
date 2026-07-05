import keyword
import re
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel


class Identifier(BaseModel):
    type: str | None = None
    value: str | None = None


class ValueEntry(BaseModel):
    value: str | None = None
    type: str | None = None


_NON_IDENT = re.compile(r"[^a-z0-9_]+")


def _normalize(key: str) -> str:
    """Normalise an API key to a Python-identifier attribute name.

    Drops a leading ``@``, lowercases, collapses runs of non-identifier characters to ``_``, and
    escapes Python keywords / leading digits. So ``@datatype`` -> ``datatype``, ``from`` -> ``from_``,
    ``PID (external)`` -> ``pid_external``. This is what lets *every* key be reached by attribute
    access and shown with a copy-pasteable label in a print, no matter how the backend spelled it.
    """
    name = key[1:] if key.startswith("@") else key
    name = _NON_IDENT.sub("_", name.lower()).strip("_")
    if not name:
        return name
    if keyword.iskeyword(name):
        return name + "_"
    if name[0].isdigit():
        return "_" + name
    return name


def _identifier_value(identifiers: list[dict[str, Any]], type_: str) -> str | None:
    return next((i.get("value") for i in identifiers if i.get("type") == type_), None)


def _identifiers(data: Any) -> list[dict[str, Any]]:
    ids = data.get("identifier") if isinstance(data, dict) else None
    if ids is None:
        return []
    items = ids if isinstance(ids, list) else [ids]
    return [i for i in items if isinstance(i, dict)]


def _resolve(data: dict[str, Any], name: str) -> tuple[bool, Any]:
    """Resolve an attribute ``name`` against a source dict.

    An exact match always wins; then ``@``-prefixed keys (``datatype`` -> ``@datatype``), then reserved
    words with a trailing underscore (``from_`` -> ``from``), and finally any key whose :func:`_normalize`
    equals ``name`` (``pid_external`` -> ``PID (external)``). Item access keeps using literal keys, so a
    normalisation collision is always resolvable with ``node["exact key"]``.
    """
    if name in data:
        return True, data[name]
    at_name = "@" + name
    if at_name in data:
        return True, data[at_name]
    if name.endswith("_") and name[:-1] in data:
        return True, data[name[:-1]]
    for key in data:
        if isinstance(key, str) and _normalize(key) == name:
            return True, data[key]
    return False, None


def _wrap(data: Any) -> "Node":
    """Wrap a fragment for navigation, promoting any ``@entity: reference`` dict to a typed :class:`Reference`.

    This is what makes references surface as references *everywhere* -- at any depth, in any model -- without
    a field having to be declared for them.
    """
    if isinstance(data, dict) and data.get("@entity") == "reference":
        return Reference(data)
    return Node(data)


def _value_of(data: Any) -> Any:
    """The ``value`` of a value-entry dict, or the scalar itself; ``None`` for lists."""
    if isinstance(data, dict):
        return data.get("value")
    return None if isinstance(data, list) else data


def _dig(data: Any, *keys: str) -> Any:
    """Follow ``keys`` through nested dicts, returning ``None`` if the path breaks."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


# Display-only cap for long scalar strings in a print; navigation/`raw` always return the full value
_MAX_STR = 120


def _scalar(value: Any) -> str:
    if isinstance(value, str) and len(value) > _MAX_STR:
        return f"{value[:_MAX_STR]!r}…(+{len(value) - _MAX_STR} chars)"
    return repr(value)


def _pascal(name: str) -> str:
    """PascalCase a (normalised) key/type name for use as a repr class label."""
    return "".join(p[:1].upper() + p[1:] for p in _normalize(name).split("_") if p) or "Node"


def _class_name(data: dict[str, Any], key_hint: str | None) -> str:
    """The class label a dict fragment prints under, as lightweight documentation of its shape.

    An ``@entity: reference`` reports what it links to (``base == "concept"`` -> ``ConceptReference``);
    any other ``@entity`` names itself (``lifecycle`` -> ``Lifecycle``); otherwise the key it sits under
    stands in (``summary`` -> ``Summary``), falling back to ``Node``.
    """
    if data.get("@entity") == "reference":
        base = _dig(data, "@datatype", "base")
        return f"{_pascal(base)}Reference" if base else "Reference"
    entity = data.get("@entity")
    if isinstance(entity, str) and entity:
        return _pascal(entity)
    return _pascal(key_hint) if key_hint else "Node"


# Target line width: a node renders inline when it fits within this column, and breaks onto indented
# lines (recursively) when it doesn't -- so small objects stay compact and complex ones open up
_WIDTH = 100


def _flat(data: Any, key_hint: str | None = None, name: str | None = None) -> str:
    """Single-line pydantic-style rendering: ``ClassName(field=..., ...)``, lists as ``[...]``, scalars
    via :func:`_scalar` (so long strings keep their ``…(+N chars)`` tail)."""
    if isinstance(data, dict):
        body = ", ".join(f"{_normalize(k)}={_flat(v, k)}" for k, v in data.items())
        return f"{name or _class_name(data, key_hint)}({body})"
    if isinstance(data, list):
        return "[" + ", ".join(_flat(v, key_hint) for v in data) + "]"
    return _scalar(data)


def _render(data: Any, indent: int, col: int, key_hint: str | None = None, name: str | None = None) -> str:
    """Render a fragment, breaking onto indented lines only where the inline form would overflow ``_WIDTH``.

    ``indent`` is the column the current line is indented to (where a closing ``)``/``]`` aligns); ``col`` is
    the column this value's first character lands on (after any ``key=`` prefix), used for the fit test.
    """
    flat = _flat(data, key_hint, name)
    if col + len(flat) <= _WIDTH:
        return flat
    child = indent + 2
    pad = " " * child
    if isinstance(data, dict) and data:
        lines = []
        for k, v in data.items():
            prefix = f"{pad}{_normalize(k)}="
            lines.append(prefix + _render(v, child, len(prefix), k))
        return f"{name or _class_name(data, key_hint)}(\n" + ",\n".join(lines) + f"\n{' ' * indent})"
    if isinstance(data, list) and data:
        lines = [pad + _render(v, child, child, key_hint) for v in data]
        return "[\n" + ",\n".join(lines) + f"\n{' ' * indent}]"
    return flat


class Node:
    """A lenient, shape-aware view over a fragment of an NG ``_source``.

    Wraps any part of the schemaless response (dict, list, or scalar) so it can be navigated by attribute
    or item access *without declaring a model in advance*. Missing keys yield an empty ``Node`` rather than
    raising, so deep chains never blow up; the untouched fragment is always on :attr:`raw`.

    NG reuses a handful of shapes across every entity type, and navigation understands them:

    * every key is reachable as an attribute with its :func:`_normalize`\\d name -- ``@``-prefixed keys with
      the ``@`` dropped (``node.datatype``), reserved words with a trailing underscore (``node.from_``), and
      awkward keys pythonised (``node.pid_external`` for ``"PID (external)"``); item access still takes exact keys.
    * ``@entity: reference`` dicts are promoted to :class:`Reference` automatically, at any depth.
    * ``{"value", "type"}`` value entries -> :attr:`value` / :attr:`values`.
    * single-object-or-list fields -> iterating/indexing normalises both.

    Printing a ``Node`` renders the fragment pydantic-style -- ``ClassName(field=..., ...)`` -- with every
    key at every level shown, so what the document actually contains is visible at a glance.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Any) -> None:
        self._data = data

    @property
    def raw(self) -> Any:
        """The wrapped fragment, exactly as returned by the API."""
        return self._data

    def _key(self, name: str) -> "Node":
        if isinstance(self._data, dict):
            found, value = _resolve(self._data, name)
            if found:
                return _wrap(value)
        return Node(None)

    def __getattr__(self, name: str) -> "Node":
        if name.startswith("_"):
            raise AttributeError(name)
        return self._key(name)

    def __getitem__(self, key: str | int) -> "Node":
        if isinstance(key, int):
            if isinstance(self._data, list) and -len(self._data) <= key < len(self._data):
                return _wrap(self._data[key])
            return Node(None)
        return self._key(key)

    def __iter__(self) -> "Iterator[Node]":
        if self._data is None:
            return
        items = self._data if isinstance(self._data, list) else [self._data]
        for item in items:
            yield _wrap(item)

    def __len__(self) -> int:
        if isinstance(self._data, (list, dict, str)):
            return len(self._data)
        return 0 if self._data is None else 1

    def __bool__(self) -> bool:
        return bool(self._data)

    def __contains__(self, key: object) -> bool:
        if isinstance(self._data, (dict, list)):
            return key in self._data
        if isinstance(self._data, str):
            return isinstance(key, str) and key in self._data
        return False

    def __eq__(self, other: object) -> bool:
        # Compare by wrapped value so a leaf reads naturally against a scalar (`node == "Vincent"`) and two
        # nodes over the same fragment are equal.
        return self._data == (other._data if isinstance(other, Node) else other)

    __hash__ = None  # type: ignore[assignment]

    def __dir__(self) -> list[str]:
        names = set(super().__dir__())
        if isinstance(self._data, dict):
            names.update(n for k in self._data if isinstance(k, str) and (n := _normalize(k)))
        return sorted(names)

    def __repr__(self) -> str:
        return _render(self._data, 0, 0)

    def __str__(self) -> str:
        # A leaf node reads as its scalar (so `f"{node}"` prints the value, not its quoted repr); containers and
        # absent nodes fall back to the structural repr.
        if isinstance(self._data, (dict, list)) or self._data is None:
            return repr(self)
        return str(self._data)

    @property
    def value(self) -> Any:
        """The ``value`` of a value-entry dict, or the scalar itself; ``None`` for lists/absent nodes."""
        return _value_of(self._data)

    @property
    def values(self) -> list[Any]:
        """Every non-null :attr:`value`, treating a lone entry as a one-item list."""
        items = self._data if isinstance(self._data, list) else [self._data]
        return [v for v in (_value_of(i) for i in items) if v is not None]

    def get(self, key: str | int, default: Any = None) -> "Node":
        """Like ``[key]`` but wraps ``default`` when the key/index is absent."""
        node = self[key]
        return node if node.raw is not None else Node(default)

    def ref(self) -> "Reference | None":
        """This node as a single :class:`Reference`, or ``None`` if it isn't a reference dict."""
        return next(iter(self.refs()), None)

    def refs(self) -> list["Reference"]:
        """Every reference here as a :class:`Reference`, normalising the single-object-or-list shape."""
        items = self._data if isinstance(self._data, list) else [self._data]
        return [Reference(i) for i in items if isinstance(i, dict)]

    def as_[T: BaseModel](self, model: type[T]) -> T:
        """Validate this fragment into ``model`` on demand -- opt into typing per field, not up front."""
        return model.model_validate(self._data)

    def as_list[T: BaseModel](self, model: type[T]) -> list[T]:
        """Validate each item (single-or-list normalised) into ``model``."""
        if self._data is None:
            return []
        items = self._data if isinstance(self._data, list) else [self._data]
        return [model.model_validate(i) for i in items]


class _Summarised(Node):
    """Node carrying the summary shape shared by entities and references (``summary``/``@admin``/``@datatype``)."""

    __slots__ = ()

    @property
    def title(self) -> str | None:
        """The entity/reference's summary label (``summary.title``)."""
        return _dig(self._data, "summary", "title")

    @property
    def uid(self) -> str | None:
        """The stable admin identifier (``@admin.uid``)."""
        return _dig(self._data, "@admin", "uid")

    @property
    def base(self) -> str | None:
        """The base type (``@datatype.base``): ``"object"``, ``"agent"``, ``"publication"``, ..."""
        return _dig(self._data, "@datatype", "base")

    @property
    def actual(self) -> str | None:
        """The specific subtype (``@datatype.actual``): ``"Painting"``, ``"Monograph"``, ..."""
        return _dig(self._data, "@datatype", "actual")


class Reference(_Summarised):
    """A summary link to another entity -- the ``@entity: reference`` pattern.

    Deliberately *not* the full entity. A reference carries the linked entity's summary (:attr:`title`),
    identity (:attr:`uid`), and type (:attr:`base`/:attr:`actual`), plus edge-specific relationship metadata
    reachable at ``.link`` (i.e. ``@link``). :attr:`base` says which entity type to fetch for the rest, and
    anything the backend inlined -- nested references included -- stays reachable by navigation/`raw`.
    """

    __slots__ = ()

    @property
    def link(self) -> Node:
        """Edge-specific relationship metadata (``@link``)."""
        return self["@link"]

    def __repr__(self) -> str:
        base = self.base
        name = f"{_pascal(base)}Reference" if base else "Reference"
        if isinstance(self._data, dict):
            return _render(self._data, 0, 0, name=name)
        return f"{name}({_scalar(self._data)})"


class Entity(_Summarised):
    """Base for entities returned by the search API.

    Modelled loosely: the backend is schemaless, so only the guaranteed summary/identity accessors are
    declared and everything else is reached by navigating the entity itself (it *is* a :class:`Node`).
    The untouched ``_source`` is always on :attr:`raw`, and printing an entity renders every key at every
    level. Add curated ``@property`` accessors on a subtype later and they transparently win over navigation.
    """

    __slots__ = ()

    @property
    def pid(self) -> str | None:
        return _identifier_value(_identifiers(self._data), "PID")

    @property
    def external_ids(self) -> list[str]:
        return [i["value"] for i in _identifiers(self._data) if i.get("type") == "PID (external)" and i.get("value")]

    def __getattr__(self, name: str) -> "Node":
        # Stricter than `Node`: a genuinely absent top-level key raises rather than yielding an empty node, so
        # `hasattr`/duck-typing stays honest at the entity level. Once a present key is wrapped, navigation from
        # there is lenient again (deep chains never blow up).
        if name.startswith("_"):
            raise AttributeError(name)
        if isinstance(self._data, dict):
            found, value = _resolve(self._data, name)
            if found:
                return _wrap(value)
        raise AttributeError(name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and self.pid is not None and self.pid == other.pid

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.pid))

    def __repr__(self) -> str:
        name = type(self).__name__
        if isinstance(self._data, dict):
            return _render(self._data, 0, 0, name=name)
        return f"{name}({_scalar(self._data)})"

    @classmethod
    def from_hit(cls, hit: dict[str, Any]):
        source = hit.get("_source", hit) if isinstance(hit, dict) else hit
        return cls(source)

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> list:
        hits = payload.get("hits", {}).get("hits", [])
        return [cls.from_hit(hit) for hit in hits]


class Agent(Entity):
    """Shared base for the two agent subtypes -- carries the ``name`` list common to both."""

    __slots__ = ()

    @property
    def names(self) -> list[str]:
        return self["name"].values


class Person(Agent):
    __slots__ = ()

    @property
    def dates(self) -> str | None:
        return self["date"][0].value


class Organisation(Agent):
    __slots__ = ()

    @property
    def websites(self) -> list[str]:
        return self["web"]["url"].values

    @property
    def address(self) -> Node | None:
        node = self["address"]
        return node if node.raw is not None else None


class Creation(Node):
    """A creation event on a work: maker references reachable as :class:`Reference`\\s."""

    __slots__ = ()

    @property
    def makers(self) -> list["Reference"]:
        return self["maker"].refs()


class Work(Entity):
    __slots__ = ()

    @property
    def creation(self) -> list["Creation"]:
        return [Creation(c.raw) for c in self["creation"]]

    @property
    def object_number(self) -> str | None:
        return _identifier_value(_identifiers(self._data), "object number")

    @property
    def makers(self) -> list[str]:
        creations = self.creation
        if not creations:
            return []
        return [t for m in creations[0].makers if (t := m.title)]

    @property
    def date(self) -> str | None:
        creations = self.creation
        return creations[0]["date"][0].value if creations else None


class Event(Entity):
    __slots__ = ()

    @property
    def names(self) -> list[str]:
        return self["name"].values

    @property
    def dates(self) -> str | None:
        return self["date"][0].value


class Exhibition(Entity):
    __slots__ = ()

    @property
    def dates(self) -> str | None:
        return self["date"][0].value

    @property
    def venues(self) -> list["Reference"]:
        return self["venue"].refs()


class Concept(Entity):
    __slots__ = ()

    @property
    def terms(self) -> list[str]:
        return self["term"].values

    @property
    def parent(self) -> str | None:
        refs = self["parent"].refs()
        return refs[0].title if refs else None


class Place(Entity):
    __slots__ = ()

    @property
    def terms(self) -> list[str]:
        return self["term"].values

    @property
    def parent(self) -> str | None:
        refs = self["parent"].refs()
        return refs[0].title if refs else None

    @property
    def coordinate(self) -> tuple[float, float] | None:
        for c in self["coordinates"]:
            lat = c["latitude"].value
            lng = c["longitude"].value
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                return float(lat), float(lng)
        return None


class Location(Entity):
    __slots__ = ()

    @property
    def names(self) -> list[str]:
        return self["name"].values


class Package(Entity):
    __slots__ = ()

    @property
    def object_titles(self) -> list[str]:
        return [t for r in self["object"].refs() if (t := r.title)]


class Publication(Entity):
    __slots__ = ()

    @property
    def date(self) -> str | None:
        return self["creation"][0]["date"][0].value

    @property
    def publisher(self) -> str | None:
        return self["creation"][0]["publisher"][0]["name"][0].value

    @property
    def place_of_publication(self) -> str | None:
        return self["creation"][0]["place"][0]["name"][0].value

    @property
    def authors(self) -> list[str]:
        return [t for r in self["work"]["creation"]["maker"].refs() if (t := r.title)]


class Archive(Entity):
    __slots__ = ()

    @property
    def level_value(self) -> str | None:
        return self["level"].value

    @property
    def parent(self) -> str | None:
        refs = self["parent"].refs()
        return refs[0].title if refs else None

    @property
    def repository(self) -> str | None:
        return self["repository"][0]["name"][0].value

    @property
    def date(self) -> str | None:
        return self["creation"]["date"][0].value


class Media(Entity):
    __slots__ = ()

    @property
    def media_type(self) -> str | None:
        return self["source"]["@type"].value

    @property
    def url(self) -> str | None:
        return self["source"]["@location"].value


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
    datatype: dict[str, Any] = source.get("@datatype") or {}
    base = datatype.get("base", "")
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
    "Archive",
    "Concept",
    "Entity",
    "Event",
    "Exhibition",
    "Identifier",
    "Location",
    "Media",
    "Node",
    "Organisation",
    "Package",
    "Person",
    "Place",
    "Publication",
    "Reference",
    "ValueEntry",
    "Work",
    "model_for",
    "parse_hit",
    "parse_response",
]
