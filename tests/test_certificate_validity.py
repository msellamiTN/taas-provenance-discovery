from taas.certificate import Certificate


def make_certificate(checks):
    return Certificate(
        toolkit=[],
        checks=checks,
        witnesses={},
        regime="exact",
        cost=0.0,
        util=1.0,
        bridge_ratio=0.0,
        bindings={},
    )


def test_certificate_valid_requires_every_mandatory_check_to_be_true():
    mandatory = {name: True for name in ("S", "C", "P", "E", "L", "V")}
    assert make_certificate(mandatory).valid

    for name in mandatory:
        broken = mandatory | {name: False}
        assert not make_certificate(broken).valid


def test_certificate_valid_fails_closed_for_missing_or_non_boolean_checks():
    mandatory = {name: True for name in ("S", "C", "P", "E", "L", "V")}
    del mandatory["V"]
    assert not make_certificate(mandatory).valid

    non_boolean = {name: True for name in ("S", "C", "P", "E", "L", "V")}
    non_boolean["S"] = 1
    assert not make_certificate(non_boolean).valid


def test_minimality_and_bridge_metrics_are_diagnostics_not_validity_gates():
    checks = {name: True for name in ("S", "C", "P", "E", "L", "V")}
    checks.update({"M": False, "B": False})
    assert make_certificate(checks).valid
