import pytest

from taas.effects import Effect
from taas.policy import Policy, read_only_policy
from taas.studio.execution_gateway import ApprovalStore, GatewayDenied, policy_fingerprint, require_policy_allow


def test_gateway_denies_missing_policy_and_empty_effects():
    with pytest.raises(GatewayDenied, match="No trusted"):
        require_policy_allow(None, ["read(db)"])
    with pytest.raises(GatewayDenied, match="not fully allowed"):
        require_policy_allow(read_only_policy(), ["write(db)"])
    with pytest.raises(GatewayDenied, match="not fully allowed"):
        require_policy_allow(read_only_policy(), [])


def test_gateway_uses_existing_scoped_effect_policy():
    policy = Policy.make("docs-read", allowed=["read(docs)", "session"])
    assert require_policy_allow(policy, [Effect("read", "docs/page")]) == frozenset({
        Effect("read", "docs/page")
    })
    with pytest.raises(GatewayDenied):
        require_policy_allow(policy, ["read(database)"])


def test_approval_is_bound_to_actor_server_tool_arguments_goal_and_policy():
    store = ApprovalStore(secret=b"x" * 32)
    policy = read_only_policy()
    args = {"query": "project status"}
    goal = {"prompt": "Find project status", "goals": [{"id": "g1"}]}
    approval = store.issue(actor="operator-1", server_id="docs", tool_name="search",
                           arguments=args, goal_spec=goal, policy=policy, effects=["read(docs)"], tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)

    with pytest.raises(GatewayDenied, match="does not match"):
        store.consume(approval.token, actor="operator-2", server_id="docs", tool_name="search",
                      arguments=args, goal_spec=goal, policy=policy, tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)

    # A mismatch consumes the token; it cannot be retried with changed context.
    with pytest.raises(GatewayDenied, match="missing, expired, or already consumed"):
        store.consume(approval.token, actor="operator-1", server_id="docs", tool_name="search",
                      arguments=args, goal_spec=goal, policy=policy, tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)


def test_approval_is_one_time_and_rejects_argument_tampering():
    store = ApprovalStore(secret=b"y" * 32)
    policy = read_only_policy()
    args = {"path": "public/report.txt"}
    goal = {"prompt": "Read report"}
    approval = store.issue(actor="u1", server_id="files", tool_name="read_file",
                           arguments=args, goal_spec=goal, policy=policy, effects=["read(fs)"], tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)

    with pytest.raises(GatewayDenied, match="does not match"):
        store.consume(approval.token, actor="u1", server_id="files", tool_name="read_file",
                      arguments={"path": "../../secret"}, goal_spec=goal, policy=policy, tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)

    # The approval was consumed by the failed attempt.
    with pytest.raises(GatewayDenied):
        store.consume(approval.token, actor="u1", server_id="files", tool_name="read_file",
                      arguments=args, goal_spec=goal, policy=policy, tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)


def test_approval_invalidated_when_policy_changes():
    store = ApprovalStore(secret=b"z" * 32)
    policy = read_only_policy()
    approval = store.issue(actor="u1", server_id="docs", tool_name="search",
                           arguments={"q": "x"}, goal_spec={"prompt": "x"},
                           policy=policy, effects=["read(docs)"], tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)
    changed = Policy.make("changed", allowed=["read(other)"])
    assert policy_fingerprint(changed) != policy_fingerprint(policy)
    with pytest.raises(GatewayDenied, match="does not match"):
        store.consume(approval.token, actor="u1", server_id="docs", tool_name="search",
                      arguments={"q": "x"}, goal_spec={"prompt": "x"}, policy=changed, tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)


def test_approval_rejects_side_effects_not_allowed_by_policy():
    store = ApprovalStore(secret=b"a" * 32)
    with pytest.raises(GatewayDenied):
        store.issue(actor="u1", server_id="shell", tool_name="run",
                    arguments={"cmd": "whoami"}, goal_spec={"prompt": "inspect"},
                    policy=read_only_policy(), effects=["exec"], tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64)



def test_approval_rejects_stale_tool_definition_and_assurance_evidence():
    store = ApprovalStore(secret=b"c" * 32)
    policy = read_only_policy()
    approval = store.issue(
        actor="u1", server_id="docs", tool_name="search",
        arguments={"q": "x"}, goal_spec={"prompt": "x"},
        policy=policy, effects=["read(docs)"],
        tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64,
    )
    with pytest.raises(GatewayDenied, match="does not match"):
        store.consume(
            approval.token, actor="u1", server_id="docs", tool_name="search",
            arguments={"q": "x"}, goal_spec={"prompt": "x"}, policy=policy,
            tool_definition_hash="c" * 64, assurance_evidence_hash="b" * 64,
        )

    approval = store.issue(
        actor="u1", server_id="docs", tool_name="search",
        arguments={"q": "x"}, goal_spec={"prompt": "x"},
        policy=policy, effects=["read(docs)"],
        tool_definition_hash="a" * 64, assurance_evidence_hash="b" * 64,
    )
    with pytest.raises(GatewayDenied, match="does not match"):
        store.consume(
            approval.token, actor="u1", server_id="docs", tool_name="search",
            arguments={"q": "x"}, goal_spec={"prompt": "x"}, policy=policy,
            tool_definition_hash="a" * 64, assurance_evidence_hash="d" * 64,
        )


def test_policy_fingerprint_covers_visibility_and_declassification():
    from taas.policy import Declassification
    base = Policy.make("p", allowed=["read(*)"])
    changed = Policy.make(
        "p", allowed=["read(*)"], visible=frozenset({"tool-a"}),
        declass=(Declassification("private", "internal", min_records=20),),
    )
    assert policy_fingerprint(base) != policy_fingerprint(changed)


def test_effects_must_be_a_collection_not_a_string():
    with pytest.raises(GatewayDenied, match="collection"):
        require_policy_allow(read_only_policy(), "read(db)")


def test_approval_requires_sha256_contract_and_evidence_hashes():
    store = ApprovalStore(secret=b"d" * 32)
    with pytest.raises(GatewayDenied, match="SHA-256"):
        store.issue(
            actor="u1", server_id="docs", tool_name="search",
            arguments={}, goal_spec={}, policy=read_only_policy(),
            effects=["read(docs)"], tool_definition_hash="not-a-hash",
            assurance_evidence_hash="b" * 64,
        )
