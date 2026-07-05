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
    render_candidates,
    to_context,
)
from national_gallery_api.models import _BY_BASE
from national_gallery_api.rendering import _GENERIC, _SPECS

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
)


def test_person_render_format():
    p = Person.from_hit({"_source": PERSON_SOURCE})
    rendered = to_context(p)
    assert rendered.splitlines()[0] == f"Person: {p.title}"
    assert f"  PID: {p.pid}" in rendered
    assert f"  Subtype: {p.actual}" in rendered
    assert f"  Dates: {p.dates}" in rendered
    assert f"  Names: {'; '.join(p.names)}" in rendered
    assert f"  External IDs: {'; '.join(sorted(p.external_ids))}" in rendered


def test_render_omits_empty_fields():
    rendered = to_context(Person.from_hit({"_source": {"summary": {"title": "Anon"}}}))
    assert rendered == "Person: Anon"
    assert "PID" not in rendered
    assert "Dates" not in rendered


def test_render_unknown_title_placeholder():
    rendered = to_context(Person.from_hit({"_source": {}}))
    assert rendered.startswith("Person: (unknown)")


def test_organisation_render():
    o = Organisation.from_hit({"_source": ORGANISATION_SOURCE})
    rendered = to_context(o)
    assert rendered.startswith(f"Organisation: {o.title}")
    assert f"  Location: {o.address.city}, {o.address.country}" in rendered
    assert f"  Websites: {'; '.join(o.websites)}" in rendered


def test_work_render():
    w = Work.from_hit({"_source": WORK_SOURCE})
    rendered = to_context(w)
    assert f"Work: {w.title}" in rendered
    assert f"  Object number: {w.object_number}" in rendered
    assert f"  Makers: {'; '.join(w.makers)}" in rendered
    assert f"  Date: {w.date}" in rendered


def test_each_type_renders_with_its_header():
    cases = [
        (Event, EVENT_SOURCE, "Event:"),
        (Exhibition, EXHIBITION_SOURCE, "Exhibition:"),
        (Place, PLACE_SOURCE, "Place:"),
        (Location, LOCATION_SOURCE, "Location:"),
        (Concept, CONCEPT_SOURCE, "Concept:"),
        (Publication, PUBLICATION_SOURCE, "Publication:"),
        (Archive, ARCHIVE_SOURCE, "Archive:"),
        (Media, MEDIA_SOURCE, "Media:"),
        (Package, PACKAGE_SOURCE, "Package:"),
    ]
    for model, source, header in cases:
        rendered = to_context(model.from_hit({"_source": source}))
        assert rendered.startswith(header)
        assert "  PID:" in rendered


def test_place_render_includes_coordinates():
    p = Place.from_hit({"_source": PLACE_SOURCE})
    rendered = to_context(p)
    lat, lng = p.coordinate
    assert f"  Coordinates: {lat}, {lng}" in rendered
    assert f"  Within: {p.parent}" in rendered


def test_every_concrete_type_has_a_dedicated_renderer():
    # Guard against `model_for` gaining a type without a matching `_SPECS` entry,
    # which would silently fall back to the generic (`_GENERIC`) `Entity` renderer.
    concrete = set(_BY_BASE.values()) | {Person, Organisation}
    missing = [t.__name__ for t in concrete if _SPECS.get(t, _GENERIC) is _GENERIC]
    assert not missing, f"types falling back to the generic Entity renderer: {missing}"


def test_base_entity_render_fallback():
    # An Entity that isn't a registered subtype uses the generic renderer.
    e = Entity.from_hit({"_source": {"summary": {"title": "Thing"}, "@datatype": {"base": "mystery"}}})
    rendered = to_context(e)
    assert rendered.startswith("Entity: Thing")
    assert "  Type: mystery" in rendered


def test_render_candidates_orders_by_pid_and_dedupes():
    a = Person.from_hit({"_source": {**PERSON_SOURCE, "identifier": [{"type": "PID", "value": "BBB"}]}})
    b = Person.from_hit({"_source": {**PERSON_SOURCE, "identifier": [{"type": "PID", "value": "AAA"}]}})
    dup_a = Person.from_hit({"_source": {**PERSON_SOURCE, "identifier": [{"type": "PID", "value": "BBB"}]}})

    rendered = render_candidates([a, b, dup_a])
    assert rendered.count("Candidate") == 2  # dup_a removed
    assert rendered.index("AAA") < rendered.index("BBB")  # sorted by PID
    assert rendered.startswith("Candidate 1:")


def test_render_candidates_is_deterministic_regardless_of_input_order():
    a = Person.from_hit({"_source": {**PERSON_SOURCE, "identifier": [{"type": "PID", "value": "AAA"}]}})
    b = Person.from_hit({"_source": {**PERSON_SOURCE, "identifier": [{"type": "PID", "value": "BBB"}]}})
    assert render_candidates([a, b]) == render_candidates([b, a])


def test_render_candidates_skips_entities_without_pid():
    no_pid = Person.from_hit({"_source": {"summary": {"title": "Anon"}}})
    assert render_candidates([no_pid]) == "No candidates."


def test_render_candidates_empty():
    assert render_candidates([]) == "No candidates."
