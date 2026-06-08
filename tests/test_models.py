"""Model-parsing tests.

Each happy-path test drives a model from a real captured document and asserts
its accessors against values read straight back out of that document (via the
`conftest` helpers), so the assertions hold for whatever the live API currently
returns. Tests of *absent* fields and dispatch/identity logic use small inline
documents — those are minimal inputs to exercise a branch, not stand-ins for an
API response.
"""

from national_gallery_api import (
    Archive,
    Concept,
    Entity,
    Event,
    Exhibition,
    Location,
    Media,
    Organisation,
    Package,
    Person,
    Place,
    Publication,
    Work,
    model_for,
    parse_hit,
    parse_response,
)

from .conftest import (
    ARCHIVE_SOURCE,
    CONCEPT_SOURCE,
    EVENT_SOURCE,
    EXHIBITION_SOURCE,
    LOCATION_SOURCE,
    MEDIA_SOURCE,
    ORGANISATION_SOURCE,
    PACKAGE_SOURCE,
    PERSON_SOURCE,
    PLACE_SOURCE,
    PUBLICATION_SOURCE,
    WORK_SOURCE,
    es_payload,
    identifier_of,
    named_value,
    pid_of,
    titles_of,
    value_list,
)


def test_person_fields():
    src = PERSON_SOURCE
    p = Person.from_hit({"_source": src})
    assert p.title == src["summary"]["title"]
    assert p.pid == pid_of(src)
    assert p.names == value_list(src["name"])
    assert p.dates == src["date"][0]["value"]
    assert p.datatype is not None
    assert p.datatype.base == src["@datatype"]["base"]
    assert p.datatype.actual == src["@datatype"]["actual"]


def test_person_external_ids_only_external_type():
    src = PERSON_SOURCE
    p = Person.from_hit({"_source": src})
    expected = [i["value"] for i in src["identifier"] if i["type"] == "PID (external)"]
    assert expected, "captured person should exercise external IDs"
    assert p.external_ids == expected
    assert p.pid not in p.external_ids


def test_raw_preserves_source():
    p = Person.from_hit({"_source": PERSON_SOURCE})
    assert p.raw == PERSON_SOURCE


def test_from_hit_without_source_wrapper():
    # A bare document (no `_source` envelope) is accepted as-is.
    p = Person.from_hit(PERSON_SOURCE)
    assert p.pid == pid_of(PERSON_SOURCE)


def test_missing_fields_default_safely():
    p = Person.from_hit({"_source": {}})
    assert p.pid is None
    assert p.title is None
    assert p.names == []
    assert p.dates is None
    assert p.external_ids == []


def test_organisation_fields():
    src = ORGANISATION_SOURCE
    o = Organisation.from_hit({"_source": src})
    assert o.names == value_list(src["name"])
    assert o.websites == value_list(src["web"]["url"])
    assert o.address is not None
    assert o.address.city == src["address"]["city"]
    assert o.address.country == src["address"]["country"]


def test_organisation_without_web_or_address():
    o = Organisation.from_hit({"_source": {"identifier": [{"type": "PID", "value": "x"}]}})
    assert o.websites == []
    assert o.address is None


def test_work_fields():
    src = WORK_SOURCE
    w = Work.from_hit({"_source": src})
    creation = src["creation"][0]
    first_biblio = src["bibliography"][0]
    assert w.title == src["summary"]["title"]
    assert w.object_number == identifier_of(src, "object number")
    assert w.makers == titles_of(creation["maker"])
    assert w.date == creation["date"][0]["value"]
    assert w.bibliography[0].title == first_biblio["summary"]["title"]
    assert str(w.bibliography[0].page) == str(first_biblio["@link"]["details"]["page"])


def test_work_without_creation():
    w = Work.from_hit({"_source": {"summary": {"title": "Untitled"}}})
    assert w.makers == []
    assert w.date is None


def test_concept_fields():
    src = CONCEPT_SOURCE
    c = Concept.from_hit({"_source": src})
    assert c.terms == value_list(src["term"])
    assert c.parent == src["parent"][0]["summary"]["title"]


def test_place_coordinate_parsed_to_floats():
    src = PLACE_SOURCE
    p = Place.from_hit({"_source": src})
    first = src["coordinates"][0]
    assert p.coordinate == (float(first["latitude"]["value"]), float(first["longitude"]["value"]))
    assert p.parent == src["parent"][0]["summary"]["title"]


def test_place_without_numeric_coordinate():
    p = Place.from_hit({"_source": {"coordinates": [{"value": "somewhere"}]}})
    assert p.coordinate is None


def test_event_fields():
    src = EVENT_SOURCE
    e = Event.from_hit({"_source": src})
    assert e.names == value_list(src["name"])
    assert e.dates == src["date"][0]["value"]


def test_exhibition_fields():
    src = EXHIBITION_SOURCE
    e = Exhibition.from_hit({"_source": src})
    assert e.dates == src["date"][0]["value"]
    assert [v.title for v in e.venues] == titles_of(src["venue"])


def test_location_fields():
    src = LOCATION_SOURCE
    loc = Location.from_hit({"_source": src})
    assert loc.names == value_list(src["name"])
    assert loc.floor == src["floor"]


def test_publication_fields():
    src = PUBLICATION_SOURCE
    pub = Publication.from_hit({"_source": src})
    creation = src["creation"][0]
    assert pub.date == creation["date"][0]["value"]
    assert pub.publisher == named_value(creation["publisher"])
    assert pub.place_of_publication == named_value(creation["place"])
    assert pub.authors == titles_of(src["work"]["creation"]["maker"])


def test_archive_fields():
    src = ARCHIVE_SOURCE
    a = Archive.from_hit({"_source": src})
    assert a.level_value == src["level"]["value"]
    assert a.parent == src["parent"][0]["summary"]["title"]
    assert a.repository == named_value(src["repository"])
    assert a.date == src["creation"]["date"][0]["value"]


def test_media_fields():
    src = MEDIA_SOURCE
    m = Media.from_hit({"_source": src})
    assert m.media_type == src["source"]["@type"]
    assert m.url == src["source"]["@location"]["value"]


def test_package_fields():
    src = PACKAGE_SOURCE
    pkg = Package.from_hit({"_source": src})
    assert pkg.object_titles == titles_of(src["object"])


def test_equality_and_hash_by_pid():
    a = Person.from_hit({"_source": PERSON_SOURCE})
    b = Person.from_hit({"_source": PERSON_SOURCE})
    assert a == b
    assert hash(a) == hash(b)


def test_set_dedupes_by_pid():
    a = Person.from_hit({"_source": PERSON_SOURCE})
    b = Person.from_hit({"_source": PERSON_SOURCE})
    assert len({a, b}) == 1


def test_entities_without_pid_are_not_equal():
    a = Person.from_hit({"_source": {}})
    b = Person.from_hit({"_source": {}})
    assert a != b


def test_different_types_with_same_pid_hash_differently():
    # Hash mixes in the type name, so a Person and Work sharing a PID don't collide.
    src = {"identifier": [{"type": "PID", "value": "SHARED"}]}
    assert hash(Person.from_hit({"_source": src})) != hash(Work.from_hit({"_source": src}))


def test_model_for_dispatch():
    assert model_for(PERSON_SOURCE) is Person
    assert model_for(ORGANISATION_SOURCE) is Organisation
    assert model_for(WORK_SOURCE) is Work
    assert model_for(CONCEPT_SOURCE) is Concept
    assert model_for(MEDIA_SOURCE) is Media


def test_model_for_unknown_base_falls_back_to_entity():
    assert model_for({"@datatype": {"base": "mystery"}}) is Entity
    assert model_for({}) is Entity


def test_parse_hit_returns_correct_subclass():
    assert isinstance(parse_hit({"_source": WORK_SOURCE}), Work)
    assert isinstance(parse_hit({"_source": ORGANISATION_SOURCE}), Organisation)


def test_parse_response_maps_each_hit():
    payload = es_payload([PERSON_SOURCE, WORK_SOURCE])
    entities = parse_response(payload)
    assert [type(e) for e in entities] == [Person, Work]


def test_from_response_empty_payload():
    assert Person.from_response({}) == []
    assert parse_response({}) == []
