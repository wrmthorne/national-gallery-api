from pydantic import Field

from .base import Entity, Named, ValueEntry


class Address(Named):
    country: str | None = None
    city: str | None = None


class Web(Named):
    url: list[ValueEntry] = Field(default_factory=list)


class Agent(Entity):
    name_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="name")

    @property
    def names(self) -> list[str]:
        return [e.value for e in self.name_entries if e.value]


class Person(Agent):
    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")

    @property
    def dates(self) -> str | None:
        return self.date_entries[0].value if self.date_entries else None


class Organisation(Agent):
    web: Web | None = None
    address: Address | None = None

    @property
    def websites(self) -> list[str]:
        return [u.value for u in (self.web.url if self.web else []) if u.value]
