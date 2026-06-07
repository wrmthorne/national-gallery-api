from pydantic import Field

from .base import Entity, Reference, ValueEntry


class Location(Entity):
    name_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="name")
    floor: int | None = None
    route_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="route")
    on_display: bool | None = Field(default=None, validation_alias="location_on_display")
    historical: bool | None = None

    @property
    def names(self) -> list[str]:
        return [e.value for e in self.name_entries if e.value]

    @property
    def routes(self) -> list[str]:
        return [r.value for r in self.route_entries if r.value]


class Package(Entity):
    name: ValueEntry | None = None
    objects: list[Reference] = Field(default_factory=list, validation_alias="object")
    description: ValueEntry | None = None

    @property
    def object_titles(self) -> list[str]:
        return [o.title for o in self.objects if o.title]
