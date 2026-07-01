from pydantic import BaseModel, Field

from .base import Entity, Reference, ValueEntry


class Term(ValueEntry):
    pass


class _Axis(BaseModel):
    value: float | str | None = None


class Coordinate(BaseModel):
    latitude: _Axis | None = None
    longitude: _Axis | None = None
    value: str | None = None


class Concept(Entity):
    name_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="name")
    term_entries: list[Term] = Field(default_factory=list, validation_alias="term")
    parents: list[Reference] = Field(default_factory=list, validation_alias="parent")

    @property
    def terms(self) -> list[str]:
        return [t.value for t in self.term_entries if t.value]

    @property
    def parent(self) -> str | None:
        return self.parents[0].title if self.parents else None


class Place(Entity):
    term_entries: list[Term] = Field(default_factory=list, validation_alias="term")
    coordinates: list[Coordinate] = Field(default_factory=list)
    parents: list[Reference] = Field(default_factory=list, validation_alias="parent")

    @property
    def terms(self) -> list[str]:
        return [t.value for t in self.term_entries if t.value]

    @property
    def parent(self) -> str | None:
        return self.parents[0].title if self.parents else None

    @property
    def coordinate(self) -> tuple[float, float] | None:
        for c in self.coordinates:
            lat = c.latitude.value if c.latitude else None
            lng = c.longitude.value if c.longitude else None
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                return float(lat), float(lng)
        return None
