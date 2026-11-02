from taas.mcpbench_analyst import MCPBenchGoalAnalyst


class FakeProvider:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def get_completion(self, system_prompt, user_prompt, max_tokens, **kwargs):
        self.calls += 1
        assert "TASK (the only information source)" in user_prompt
        return ('{"ok": true}', {"prompt_tokens": 12, "completion_tokens": 8})

    def clean_and_parse_json(self, raw):
        return self.value


def test_goal_analyst_returns_validated_goal_spec_and_usage():
    payload = {
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "search", "in": ["query"], "out": "repository[]",
            "eff": ["read(*)"], "sigma": "data", "deps": [], "desc": "Find repositories"
        }]
    }
    provider = FakeProvider(payload)
    analyst = MCPBenchGoalAnalyst(provider)
    assert analyst("Find repositories") == payload
    assert provider.calls == 1
    assert analyst.last_usage["prompt_tokens"] == 12


def test_goal_analyst_rejects_unknown_dependencies():
    bad = {
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "search", "in": [], "out": "repository[]",
            "sigma": "data", "deps": ["missing"], "desc": "Search"
        }]
    }
    try:
        MCPBenchGoalAnalyst(FakeProvider(bad))("task")
    except ValueError as exc:
        assert "Unknown goal dependencies" in str(exc)
    else:
        raise AssertionError("unknown dependencies must be rejected")
