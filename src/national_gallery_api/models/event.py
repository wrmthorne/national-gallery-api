from pydantic import Field

from .base import Entity, Reference, ValueEntry


class Status(ValueEntry):
    pass


class Event(Entity):
    name_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="name")
    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")
    recurring: bool | None = None
    historical: bool | None = None

    @property
    def names(self) -> list[str]:
        return [e.value for e in self.name_entries if e.value]

    @property
    def dates(self) -> str | None:
        return self.date_entries[0].value if self.date_entries else None


class Exhibition(Entity):
    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")
    venues: list[Reference] = Field(default_factory=list, validation_alias="venue")
    organisers: list[Reference] = Field(default_factory=list, validation_alias="agent")
    status: Status | None = None

    @property
    def dates(self) -> str | None:
        return self.date_entries[0].value if self.date_entries else None
