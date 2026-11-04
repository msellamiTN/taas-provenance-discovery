import pytest
from taas.experiments.catalog import VARIANTS, load_catalog, validate_factorial


def test_catalog_contains_exactly_e1_to_e22():
    data = load_catalog()
    assert [x["id"] for x in data["experiments"]] == [f"E{i}" for i in range(1, 23)]
    assert all(x["status"] == "planned_not_run" for x in data["experiments"])


def test_factorial_is_complete():
    data = load_catalog()
    validate_factorial(data)
    assert len(data["factorial_design"]["cells"]) == 8


@pytest.mark.parametrize("name,expected", [
    ("Full_PaMCP", (1, 1, 1)),
    ("PaMCP_NoGap", (0, 1, 1)),
    ("PaMCP_Declared", (1, 0, 1)),
    ("PaMCP_NoCert", (1, 1, 0)),
])
def test_variant_factor_contracts(name, expected):
    v = VARIANTS[name]
    assert (v.G, v.P, v.S) == expected
