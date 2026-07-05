"""Dynamic, shape-aware access to un-modelled `_source` fields via `Node`.

The typed models surface only a curated slice of each (schemaless) document; these tests cover reaching
everything else without declaring it in advance.
"""

import pytest

from national_gallery_api import Node, Reference, Work
from national_gallery_api.models import ValueEntry

from .conftest import WORK_SOURCE


def test_bibliography_entry_is_a_reference_not_an_invented_type(work: Work):
    entry = work.bibliography[0]
    assert isinstance(entry, Reference)
    # It honestly reports the linked entity's type instead of masquerading as a bespoke type or a full Publication.
    assert entry.base == "publication"
    assert entry.title == WORK_SOURCE["bibliography"][0]["summary"]["title"]
    assert entry.uid == WORK_SOURCE["bibliography"][0]["@admin"]["uid"]


def test_reference_link_exposes_edge_metadata(work: Work):
    # Citation details live on the relationship (`@link`), not on the referenced publication itself.
    details = WORK_SOURCE["bibliography"][0]["@link"]["details"]
    entry = work.bibliography[0]
    assert entry.link.details.page.raw == details["page"]
    assert entry.link.details.illustrated.raw == details["illustrated"]


def test_reference_navigates_inlined_summary_fields(work: Work):
    # A maker reference inlines some summary fields; they're reachable without inventing a model for them.
    maker = work.creation[0].makers[0]
    assert isinstance(maker, Reference)
    assert maker.base == "agent"
    src_maker = WORK_SOURCE["creation"][0]["maker"][0]
    # `.value` unwraps a value-entry to its scalar directly.
    assert maker.link.role.value == src_maker["@link"]["role"]["value"]
    assert maker.date[0].value == src_maker["date"][0]["value"]


def test_reference_raw_is_preserved(work: Work):
    assert work.bibliography[0].raw == WORK_SOURCE["bibliography"][0]


def test_references_promoted_at_any_depth_without_a_declared_field(work: Work):
    # `provenance.text.author` is a reference the model never declares a field for -- it still surfaces
    # as a Reference, honestly typed, purely from navigation.
    author = work.provenance.text.author
    assert isinstance(author, Reference)
    assert author.base == "agent"
    assert author.title == WORK_SOURCE["provenance"]["text"]["author"]["summary"]["title"]


def test_nested_references_inside_a_reference_are_promoted(work: Work):
    # The `equivalents` under a bibliography reference's `@datatype` are themselves references, reachable
    # by dotted access and promoted to Reference -- nothing is stranded as an opaque dict.
    equivalents = work.bibliography[0].datatype.equivalents
    first = equivalents[0]
    assert isinstance(first, Reference)
    assert first.admin.id.raw == WORK_SOURCE["bibliography"][0]["@datatype"]["equivalents"][0]["@admin"]["id"]
    assert [type(e) for e in equivalents] == [Reference] * len(equivalents)


@pytest.fixture
def work() -> Work:
    return Work.from_hit({"_source": WORK_SOURCE})


def test_curated_property_wins_over_dynamic(work: Work):
    # `date` is a curated accessor -> stays a string, is not shadowed by dynamic node access.
    assert isinstance(work.date, str)


def test_typed_field_wins_over_dynamic(work: Work):
    # `creation` is a declared model field -> resolves to the typed list, not a Node.
    assert not isinstance(work.creation, Node)


def test_top_level_key_is_navigable(work: Work):
    # `description` is un-modelled, yet reachable; mirrors the user-facing `work.description[0].formatted`.
    expected = WORK_SOURCE["description"][0]["formatted"]
    assert work.description[0].formatted.raw == expected


def test_nested_scalar_via_dotted_access(work: Work):
    assert work.summary.title.raw == WORK_SOURCE["summary"]["title"]


def test_namespaced_key_via_dropped_at_or_item_access(work: Work):
    # `@datatype` is reachable both by dotted access with the `@` dropped and by exact item access.
    expected = WORK_SOURCE["@datatype"]["base"]
    assert work.datatype.base.raw == expected
    assert work["@datatype"]["base"].raw == expected


def test_at_prefixed_keys_dropped_at_every_level(work: Work):
    assert work.admin.uid.raw == WORK_SOURCE["@admin"]["uid"]
    # A bibliography reference's own `@`-keys drop too.
    bib = work.bibliography[0]
    assert bib.datatype.actual.raw == WORK_SOURCE["bibliography"][0]["@datatype"]["actual"]
    assert bib.entity.raw == "reference"


def test_keyword_key_escaped_with_trailing_underscore(work: Work):
    date = work.provenance.text.date
    assert date.from_.raw == WORK_SOURCE["provenance"]["text"]["date"]["from"]
    assert date["from"].raw == date.from_.raw  # item access is equivalent


def test_absent_top_level_key_raises(work: Work):
    # Keeps hasattr/duck-typing honest: genuinely missing keys are AttributeErrors, not empty nodes.
    with pytest.raises(AttributeError):
        _ = work.definitely_not_a_key
    assert not hasattr(work, "definitely_not_a_key")


def test_present_key_navigates_leniently(work: Work):
    # Once past the first hop, missing sub-keys yield empty nodes instead of raising.
    assert work.summary.nope.deeper.raw is None


def test_value_and_values_helpers():
    assert Node({"value": "x", "type": "t"}).value == "x"
    assert Node([{"value": "a"}, {"value": "b"}, {"type": "no-value"}]).values == ["a", "b"]
    assert Node("plain").value == "plain"  # bare scalar
    assert Node(None).value is None


def test_single_or_list_normalised_on_iteration():
    # The backend stores some fields as either an object or a list; iteration flattens both.
    assert [n.raw for n in Node({"value": "solo"})] == [{"value": "solo"}]
    assert [n.raw for n in Node([{"value": "a"}, {"value": "b"}])] == [{"value": "a"}, {"value": "b"}]
    assert list(Node(None)) == []


def test_refs_and_ref(work: Work):
    makers = Node(WORK_SOURCE["creation"][0]["maker"])
    refs = makers.refs()
    assert refs and all(isinstance(r, Reference) for r in refs)
    assert makers.ref() == refs[0]
    assert Node("not-a-ref").ref() is None


def test_as_and_as_list_promote_to_models():
    single = Node({"value": "hi", "type": "greeting"}).as_(ValueEntry)
    assert single.value == "hi" and single.type == "greeting"

    many = Node([{"value": "a"}, {"value": "b"}]).as_list(ValueEntry)
    assert [v.value for v in many] == ["a", "b"]


def test_indexing_and_len_and_bool():
    node = Node([10, 20, 30])
    assert node[0].raw == 10
    assert node[-1].raw == 30
    assert node[99].raw is None  # out of range -> empty node, no IndexError
    assert len(node) == 3
    assert bool(node) is True
    assert bool(Node(None)) is False
    assert bool(Node([])) is False


def test_get_with_default():
    node = Node({"a": 1})
    assert node.get("a").raw == 1
    assert node.get("missing", "fallback").raw == "fallback"


def test_contains():
    assert "a" in Node({"a": 1})
    assert "missing" not in Node({"a": 1})
    assert "x" not in Node(None)


def test_raw_round_trips(work: Work):
    # The full, untouched source is always reachable at every level.
    assert work.raw == WORK_SOURCE
    assert Node(work.raw).raw is work.raw
