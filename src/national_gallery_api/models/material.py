from pydantic import BaseModel, ConfigDict, Field

from .base import Entity, Named, Reference, ValueEntry


class PublicationCreation(Named):
    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")
    publishers: list[Named] = Field(default_factory=list, validation_alias="publisher")
    places: list[Named] = Field(default_factory=list, validation_alias="place")


class _WorkCreation(Named):
    makers: list[Reference] = Field(default_factory=list, validation_alias="maker")


class _PublishedWork(Named):
    creation: _WorkCreation | None = None


class Publication(Entity):
    creation: list[PublicationCreation] = Field(default_factory=list)
    content_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="contents")
    work: _PublishedWork | None = None

    @property
    def date(self) -> str | None:
        if not self.creation or not self.creation[0].date_entries:
            return None
        return self.creation[0].date_entries[0].value

    @property
    def publisher(self) -> str | None:
        return self.creation[0].publishers[0].name if self.creation and self.creation[0].publishers else None

    @property
    def place_of_publication(self) -> str | None:
        return self.creation[0].places[0].name if self.creation and self.creation[0].places else None

    @property
    def authors(self) -> list[str]:
        creation = self.work.creation if self.work else None
        return [m.title for m in (creation.makers if creation else []) if m.title]

    @property
    def contents(self) -> list[str]:
        return [c.value for c in self.content_entries if c.value]


class _Language(ValueEntry):
    code: str | None = None


class ArchiveCreation(Named):
    date_entries: list[ValueEntry] = Field(default_factory=list, validation_alias="date")


class Archive(Entity):
    level: ValueEntry | None = None
    parents: list[Reference] = Field(default_factory=list, validation_alias="parent")
    repositories: list[Named] = Field(default_factory=list, validation_alias="repository")
    languages: list[_Language] = Field(default_factory=list, validation_alias="language")
    creation: ArchiveCreation | None = None

    @property
    def level_value(self) -> str | None:
        return self.level.value if self.level else None

    @property
    def parent(self) -> str | None:
        return self.parents[0].title if self.parents else None

    @property
    def repository(self) -> str | None:
        return self.repositories[0].name if self.repositories else None

    @property
    def date(self) -> str | None:
        if not self.creation or not self.creation.date_entries:
            return None
        return self.creation.date_entries[0].value


class MediaLocation(ValueEntry):
    public: bool | None = None


class MediaSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    media_type: str | None = Field(default=None, validation_alias="@type")
    location: MediaLocation | None = Field(default=None, validation_alias="@location")


class Media(Entity):
    source: MediaSource | None = None

    @property
    def media_type(self) -> str | None:
        return self.source.media_type if self.source else None

    @property
    def url(self) -> str | None:
        return self.source.location.value if self.source and self.source.location else None
