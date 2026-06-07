from typing import Any

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class Identifier(BaseModel):
    type: str | None = None
    value: str | None = None


class ValueEntry(BaseModel):
    value: str | None = None
    type: str | None = None


class DataType(BaseModel):
    base: str | None = None
    actual: str | None = None


class Reference(BaseModel):
    """A nested link to another entity (the `@entity: reference` pattern)."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, validation_alias=AliasPath("summary", "title"))
    uid: str | None = Field(default=None, validation_alias=AliasPath("@admin", "uid"))
    base: str | None = Field(default=None, validation_alias=AliasPath("@datatype", "base"))
    actual: str | None = Field(default=None, validation_alias=AliasPath("@datatype", "actual"))


class Named(BaseModel):
    """Mixin for nested objects carrying a `name` list of value entries."""

    model_config = ConfigDict(populate_by_name=True)

    name_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="name")

    @property
    def name(self) -> str | None:
        return self.name_entries[0].value if self.name_entries else None


def _identifier_value(identifiers: list[Identifier], type_: str) -> str | None:
    return next((i.value for i in identifiers if i.type == type_), None)


class Entity(BaseModel):
    """Base for entities returned by the search API.

    Modelled loosely: the backend is schemaless, so only `pid` is treated as
    meaningful and everything else is optional. The untouched `_source` is kept
    on `raw` as an escape hatch for fields not surfaced as typed attributes.
    """

    model_config = ConfigDict(populate_by_name=True)

    identifiers: list[Identifier] = Field(default_factory=list, validation_alias="identifier")
    title: str | None = Field(default=None, validation_alias=AliasPath("summary", "title"))
    datatype: DataType | None = Field(default=None, validation_alias="@datatype")
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True, repr=False)

    @property
    def pid(self) -> str | None:
        return _identifier_value(self.identifiers, "PID")

    @property
    def external_ids(self) -> list[str]:
        return [i.value for i in self.identifiers if i.type == "PID (external)" and i.value]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and self.pid is not None and self.pid == other.pid

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.pid))

    @classmethod
    def from_hit(cls, hit: dict[str, Any]):
        source = hit.get("_source", hit)
        return cls.model_validate({**source, "raw": source})

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> list:
        hits = payload.get("hits", {}).get("hits", [])
        return [cls.from_hit(hit) for hit in hits]
