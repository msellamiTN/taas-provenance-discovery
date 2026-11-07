from experiments.prepare_e9_livemcpbench import build_acceptable_sets


def test_ambiguous_tool_names_expand_to_all_valid_candidate_identities():
    choices = [
        {"tool_name": "lookup", "candidate_tool_ids": ["server-a::lookup"], "identity_status": "unique"},
        {
            "tool_name": "read_file",
            "candidate_tool_ids": ["server-b::read_file", "server-c::read_file"],
            "identity_status": "ambiguous_any_candidate_accepted",
        },
    ]
    assert build_acceptable_sets(choices) == [
        ["server-a::lookup", "server-b::read_file"],
        ["server-a::lookup", "server-c::read_file"],
    ]


def test_duplicate_mentions_collapse_to_distinct_tool_sets():
    choices = [
        {"tool_name": "same", "candidate_tool_ids": ["server-a::same"]},
        {"tool_name": "same-again", "candidate_tool_ids": ["server-a::same"]},
    ]
    assert build_acceptable_sets(choices) == [["server-a::same"]]


def test_ambiguous_expansion_is_bounded():
    choices = [
        {"tool_name": f"ambiguous-{i}", "candidate_tool_ids": [f"s{i}::t", f"s{i+1}::t"]}
        for i in range(9)
    ]
    try:
        build_acceptable_sets(choices, max_alternatives=128)
    except ValueError as exc:
        assert "exceeds 128" in str(exc)
    else:
        raise AssertionError("Expected the Cartesian identity expansion bound to fail")
