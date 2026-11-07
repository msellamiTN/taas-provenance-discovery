from __future__ import annotations

from pathlib import Path

import pytest

import experiments.prepare_e8_data as prepare


def test_git_blob_sha1_uses_git_object_header():
    payload = b'{"example": true}\n'
    assert prepare.git_blob_sha1(payload) == prepare.git_blob_sha1(payload)
    assert prepare.git_blob_sha1(payload) != __import__("hashlib").sha1(payload).hexdigest()


def test_mcp_toolbench_download_is_pinned_verified_and_idempotent(tmp_path, monkeypatch):
    payload = b'[{"uuid":"fixture"}]\n'
    expected = prepare.git_blob_sha1(payload)
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_REVISION", "a" * 40)
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_FILES", {"browser/fixture.json": expected})
    calls = []

    def downloader(url: str) -> bytes:
        calls.append(url)
        assert "/" + "a" * 40 + "/data/browser/fixture.json" in url
        return payload

    raw_root = tmp_path / "data" / "raw"
    result = prepare.prepare_mcptoolbenchpp(raw_root, downloader=downloader)
    target = raw_root / "mcptoolbenchpp" / "browser.json"
    assert target.read_bytes() == payload
    assert result["downloaded"] == ["browser/fixture.json"]
    assert result["reused_verified"] == []
    assert len(calls) == 1
    assert (raw_root / "SOURCES.txt").read_text(encoding="utf-8").strip() == (
        "MCPToolBenchPP " + "a" * 40
    )

    second = prepare.prepare_mcptoolbenchpp(
        raw_root, downloader=lambda _url: pytest.fail("verified file should be reused")
    )
    assert second["downloaded"] == []
    assert second["reused_verified"] == ["browser/fixture.json"]


def test_mcp_toolbench_preparation_rejects_content_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_REVISION", "b" * 40)
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_FILES", {"browser/fixture.json": "0" * 40})
    with pytest.raises(ValueError, match="download mismatch"):
        prepare.prepare_mcptoolbenchpp(
            tmp_path / "raw", downloader=lambda _url: b"not the pinned artifact"
        )


def test_mcp_toolbench_preparation_refuses_to_overwrite_tampered_file(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_REVISION", "c" * 40)
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_FILES", {"browser/fixture.json": "1" * 40})
    root = tmp_path / "raw" / "mcptoolbenchpp"
    root.mkdir(parents=True)
    (root / "browser.json").write_bytes(b"local unverified content")
    with pytest.raises(ValueError, match="file mismatch"):
        prepare.prepare_mcptoolbenchpp(
            tmp_path / "raw", downloader=lambda _url: pytest.fail("must not overwrite")
        )


def test_existing_source_revision_conflict_is_rejected(tmp_path, monkeypatch):
    payload = b'[]'
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_REVISION", "d" * 40)
    monkeypatch.setattr(prepare, "MCPTOOLBENCH_FILES", {"browser/fixture.json": prepare.git_blob_sha1(payload)})
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    (raw_root / "SOURCES.txt").write_text("MCPToolBenchPP " + "e" * 40 + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="different MCPToolBench"):
        prepare.prepare_mcptoolbenchpp(raw_root, downloader=lambda _url: payload)
