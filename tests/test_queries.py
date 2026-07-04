from national_gallery_api import EntityType, build_free_text, build_search


def test_empty_query_is_match_all():
    body = build_search()
    assert body["query"] == {"match_all": {}}
    assert body["size"] == 10
    assert body["from"] == 0


def test_text_only_uses_match_on_title():
    body = build_search("van gogh")
    assert body["query"] == {"bool": {"must": [{"match": {"summary.title": "van gogh"}}]}}


def test_blank_text_is_ignored():
    # Falsy text must not add a match clause.
    assert build_search("")["query"] == {"match_all": {}}


def test_base_and_actual_add_term_clauses():
    body = build_search(base=EntityType.AGENT, actual="Individual")
    must = body["query"]["bool"]["must"]
    assert {"term": {"@datatype.base": "agent"}} in must
    assert {"term": {"@datatype.actual": "Individual"}} in must


def test_base_accepts_plain_string():
    body = build_search(base="object")
    assert {"term": {"@datatype.base": "object"}} in body["query"]["bool"]["must"]


def test_all_clauses_combined_in_order():
    body = build_search("sunflowers", base=EntityType.OBJECT, actual="Painting", size=3, from_=20)
    assert body["query"]["bool"]["must"] == [
        {"match": {"summary.title": "sunflowers"}},
        {"term": {"@datatype.base": "object"}},
        {"term": {"@datatype.actual": "Painting"}},
    ]
    assert body["size"] == 3
    assert body["from"] == 20


def test_free_text_matches_all_fields_without_type_filter():
    body = build_free_text("van gogh")
    # multi_match over ["*"] with no @datatype clause -> any and mixed types.
    assert body["query"] == {"multi_match": {"query": "van gogh", "fields": ["*"]}}
    assert body["size"] == 10
    assert body["from"] == 0


def test_free_text_passes_size_and_from():
    body = build_free_text("sunflowers", size=25, from_=50)
    assert body["query"]["multi_match"]["query"] == "sunflowers"
    assert body["size"] == 25
    assert body["from"] == 50


def test_entitytype_is_str_enum():
    assert str(EntityType.AGENT) == "agent"
    assert EntityType.OBJECT == "object"
