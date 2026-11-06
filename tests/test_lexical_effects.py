from taas.contracts import make_contract
from taas.effects import lexical_effects
from taas.engine import DiscoveryEngine
from taas.model_profile import ModelProfile
from taas.policy import Policy


def test_lookup_records_noun_is_not_misclassified_as_a_write():
    effects = lexical_effects(
        "lookup_records",
        "Search and return records matching a query.",
        ["query"],
    )
    effect_names = {str(effect) for effect in effects}

    assert "write(*)" not in effect_names
    assert "egress(*)" in effect_names
    assert "read(*)" in effect_names


def test_record_as_an_action_remains_a_write_effect():
    effects = lexical_effects("record_event", "Record an event in the audit log.", ["event"])
    assert "write(*)" in {str(effect) for effect in effects}


def test_read_search_tool_is_discoverable_under_read_and_egress_policy():
    effects = lexical_effects(
        "lookup_records",
        "Search and return records matching a query.",
        ["query"],
    )
    contract = make_contract(
        "sample_registry::lookup_records",
        {"query": "query"},
        "record:search_result[]",
        sorted(map(str, effects)),
        description="Search and return records matching a query.",
        source_label="public",
    )
    engine = DiscoveryEngine(
        [contract],
        ModelProfile("test", 0.8, {}, strict=True),
    )
    policy = Policy.make(
        "read-search",
        allowed=("read(*)", "egress(*)", "session"),
    )
    spec = {
        "prompt": "Retrieve records matching the provided query from the configured source.",
        "prompt_inputs": ["query"],
        "goals": [{
            "id": "g1",
            "class": "retrieve",
            "in": ["query"],
            "out": "record[]",
            "eff": ["read(sample_registry)"],
            "sigma": "data",
            "n": 1,
            "exactness": "tolerant",
            "deps": [],
            "desc": "Retrieve records matching a query from the configured source.",
        }],
    }

    result = engine.discover(spec, policy)

    assert result.abstained is False, result.counterexample
    assert result.toolkit == ["sample_registry::lookup_records"]
    assert result.certificate is not None and result.certificate.valid
    assert result.compose.stats["eligible"] == 1
    assert result.compose.stats["candidates"] == 1
