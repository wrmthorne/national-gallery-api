from pydantic import Field

from .base import Entity, ValueEntry


class Person(Entity):
    name_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="name")
    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")

    @property
    def names(self) -> list[str]:
        return [e.value for e in self.name_entries if e.value]

    @property
    def dates(self) -> str | None:
        return self.date_entries[0].value if self.date_entries else None
