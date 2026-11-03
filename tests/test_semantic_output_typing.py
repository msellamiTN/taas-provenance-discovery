from taas.types import tau_out


def _array(properties=None):
    item = {"type": "object"}
    if properties is not None:
        item["properties"] = {name: {"type": "string"} for name in properties}
    return {"type": "array", "items": item}


def test_array_output_uses_tool_name_domain_evidence():
    result = tau_out(
        "npmVersions",
        "List recent package versions from the npm registry.",
        _array(["name", "version"]),
    )
    assert str(result.type) == "record:package[]"
    assert result.confidence == 0.72
    assert result.source == "schema+lex-domain"


def test_array_output_uses_description_domain_evidence():
    result = tau_out(
        "extract_features",
        "Extract MFCC and chroma features from audio recordings.",
        _array(["name", "values"]),
    )
    assert str(result.type) == "record:audio[]"
    assert result.source == "schema+lex-domain"


def test_array_output_can_use_item_schema_field_evidence():
    result = tau_out(
        "list_entities",
        "Return matching entities.",
        _array(["package", "version"]),
    )
    assert str(result.type) == "record:package[]"


def test_array_shape_alone_stays_generic_and_uncertain():
    result = tau_out(
        "list_records",
        "Return matching items.",
        _array(["id", "created_at", "value"]),
    )
    assert str(result.type) == "record[]"
    assert result.confidence == 0.45
    assert result.source == "schema-generic"


def test_non_array_output_keeps_existing_lexical_typing():
    result = tau_out(
        "get_stock_quote",
        "Return the latest stock quote.",
        {"type": "object"},
    )
    assert str(result.type) == "record:stock"
    assert result.source == "lex-out"
