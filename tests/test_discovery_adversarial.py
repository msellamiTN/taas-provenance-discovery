"""Adversarial end-to-end checks for discovery selection and fail-closed behavior.

The broader scenario, dependency, exact-search, effect-bound, and witness-integrity
properties are covered in test_paper_results.py and test_witness_binding_integrity.py.
This module adds compact request-path regressions for alternative selection,
missing capability, and evidence thresholds.
"""
from taas.composer import ComposerConfig, CostModel
from taas.contracts import make_contract
from taas.engine import DiscoveryEngine, EngineConfig
from taas.model_profile import ModelProfile
from taas.policy import Policy


def _profile():
    # Strict mode with no calibrated classes is intentionally conservative; the
    # retrieval goal below is external (sigma=data), so no model class is needed.
    return ModelProfile("test", 0.8, {}, strict=True)


def _request(output="record:order[]"):
    return {
        "prompt": "List orders",
        "prompt_inputs": ["text", "query"],
        "goals": [{
            "id": "g1",
            "class": "retrieve",
            "in": ["query"],
            "out": output,
            "eff": ["read(db)"],
            "sigma": "data",
            "desc": "List orders",
            "deps": [],
        }],
    }


def _policy(required=(), lmin="ann"):
    return Policy.make(
        "discovery-test",
        required=required,
        allowed=("read(db)",),
        lmin=lmin,
    )


def test_multiple_compatible_tools_select_minimum_cost_valid_toolkit():
    contracts = [
        make_contract(
            "orders::list_orders_primary",
            {"query": "query"},
            "record:order[]",
            ["read(db)"],
            evidence="obs",
            description="List orders from the primary order database",
        ),
        make_contract(
            "orders::list_orders_backup",
            {"query": "query"},
            "record:order[]",
            ["read(db)"],
            evidence="obs",
            description="List orders from the backup order database",
        ),
    ]
    cfg = EngineConfig(ComposerConfig(K=5, relevance=0.0))
    engine = DiscoveryEngine(contracts, _profile(), cfg=cfg)
    result = engine.discover(_request(), _policy())

    assert not result.abstained
    assert result.certificate is not None and result.certificate.valid
    assert len(result.toolkit) == 1
    assert result.toolkit[0] in result.compose.candidates
    costs = CostModel(engine.H, result.compose.candidates, cfg.composer)
    assert abs(result.certificate.cost - min(costs(t) for t in result.compose.candidates)) < 1e-9


def test_missing_capability_abstains_without_manifest_or_certificate():
    contracts = [
        make_contract(
            "orders::list_orders",
            {"query": "query"},
            "record:order[]",
            ["read(db)"],
            evidence="obs",
            description="List orders",
        )
    ]
    engine = DiscoveryEngine(contracts, _profile())
    result = engine.discover(_request("record:customer[]"), _policy())

    assert result.abstained
    assert result.toolkit is None
    assert result.certificate is None
    assert result.manifest is None
    assert result.counterexample is not None
    assert result.counterexample.kind == "chi1"


def test_insufficient_evidence_abstains_even_when_capability_shape_matches():
    contracts = [
        make_contract(
            "orders::list_orders",
            {"query": "query"},
            "record:order[]",
            ["read(db)"],
            evidence="ann",
            description="List orders",
        )
    ]
    engine = DiscoveryEngine(contracts, _profile())
    # The contract's annotation evidence is below the policy's attestation threshold.
    result = engine.discover(_request(), _policy(required={"read_only"}, lmin="att"))

    assert result.abstained
    assert result.toolkit is None
    assert result.certificate is None
    assert result.manifest is None
    assert result.counterexample is not None
    assert result.counterexample.kind == "chi2"
