"""Tests for the read-only PaMCP Section A preflight."""
from experiments.section_a import (
    build_report,
    canonical_hash,
    main,
    protocol_check,
    sha256_file,
)


def test_canonical_hash_is_order_independent():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_protocol_check_reports_missing_file(tmp_path):
    result = protocol_check(tmp_path / "missing.md")
    assert result["status"] == "BLOCKED_DATA"


def test_build_report_is_read_only_and_does_not_promote_historical_results(tmp_path):
    protocol = tmp_path / "docs/experiment_design/PAMCP_CORE_PROTOCOL_V2.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("\n".join([
        "## 1. Research question", "## 2. PaMCP Core feature model",
        "## 3. Dataset portfolio and track separation", "## 4. Baseline protocol",
        "## 5. Ablations and factorial design", "## 6. Metrics and contracts",
    ]), encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    old = results / "e0_registry.json"
    old.write_text('{"old": true}', encoding="utf-8")
    before = sha256_file(old)

    report = build_report(tmp_path)

    assert report["mode"] == "READ_ONLY_PREFLIGHT"
    assert report["historical_results"]["classification"] == "HISTORICAL_ONLY"
    assert report["historical_results"]["files"][0]["path"] == "results/e0_registry.json"
    assert report["safety"]["legacy_experiments_executed"] is False
    assert sha256_file(old) == before


def test_cli_refuses_to_overwrite(tmp_path):
    output = tmp_path / "report.json"
    output.write_text("keep", encoding="utf-8")
    try:
        main(["--root", str(tmp_path), "--output", str(output)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("CLI should reject an existing output file")
    assert output.read_text(encoding="utf-8") == "keep"
