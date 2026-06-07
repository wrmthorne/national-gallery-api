from pydantic import AliasPath, BaseModel, ConfigDict, Field

from .base import Entity, Reference, ValueEntry, _identifier_value

Maker = Reference


class BibliographyEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, validation_alias=AliasPath("summary", "title"))
    page: str | None = Field(default=None, validation_alias=AliasPath("@link", "details", "page"))
    citation_type: str | None = Field(default=None, validation_alias=AliasPath("@link", "details", "type"))
    illustrated: bool | None = Field(default=None, validation_alias=AliasPath("@link", "details", "illustrated"))


class Creation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")
    makers: list[Reference] = Field(default_factory=list, validation_alias="maker")


class Work(Entity):
    creation: list[Creation] = Field(default_factory=list)
    bibliography: list[BibliographyEntry] = Field(default_factory=list)

    @property
    def object_number(self) -> str | None:
        return _identifier_value(self.identifiers, "object number")

    @property
    def makers(self) -> list[str]:
        if not self.creation:
            return []
        return [m.title for m in self.creation[0].makers if m.title]

    @property
    def date(self) -> str | None:
        if not self.creation or not self.creation[0].date_entries:
            return None
        return self.creation[0].date_entries[0].value
