from __future__ import annotations
import hashlib, json, sqlite3
import pytest
from pydantic import ValidationError
from taas.studio import skill_registry
from taas.studio.skill_spec import validate_skill_manifest

def manifest():
    return {"apiVersion":"taas.ai/v1alpha1","kind":"Skill",
      "metadata":{"id":"date-arithmetic","name":"Date arithmetic","version":"1.0.0",
                  "description":"Plan exact date calculations from independent sources."},
      "spec":{"instructions":"Acquire each date independently, then compute the exact difference.",
              "trigger_phrases":["date difference","year difference"],"tags":["research","calculation"]}}

def use_db(monkeypatch,tmp_path):
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH",str(tmp_path/"skills.sqlite3"))

def test_skill_manifest_validates_and_normalizes():
    result=validate_skill_manifest(manifest())
    assert result["kind"]=="Skill"
    assert result["spec"]["tags"]==["research","calculation"]

def test_skill_manifest_rejects_duplicate_triggers_and_unknown_fields():
    value=manifest(); value["spec"]["trigger_phrases"]=["Date difference","date difference"]
    with pytest.raises(ValidationError): validate_skill_manifest(value)
    value=manifest(); value["spec"]["is_authorized"]=True
    with pytest.raises(ValidationError): validate_skill_manifest(value)

def test_registry_creates_content_addressed_immutable_draft(monkeypatch,tmp_path):
    use_db(monkeypatch,tmp_path); value=validate_skill_manifest(manifest())
    saved=skill_registry.create_draft(value,actor="test")
    expected=hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    assert saved["manifest_sha256"]==expected and saved["lifecycle_state"]=="draft"
    with pytest.raises(skill_registry.SkillRegistryConflict): skill_registry.create_draft(value)

def test_registry_lifecycle_is_monotonic_and_audited(monkeypatch,tmp_path):
    use_db(monkeypatch,tmp_path); value=validate_skill_manifest(manifest())
    skill_registry.create_draft(value,actor="alice")
    validated=skill_registry.transition("date-arithmetic","1.0.0","validated",actor="reviewer")
    published=skill_registry.transition("date-arithmetic","1.0.0","published",actor="publisher")
    assert validated["lifecycle_state"]=="validated" and published["lifecycle_state"]=="published"
    with pytest.raises(skill_registry.SkillRegistryConflict):
        skill_registry.transition("date-arithmetic","1.0.0","validated")
    events=skill_registry.list_events(skill_id="date-arithmetic")
    assert [e["event_type"] for e in reversed(events["events"])]==["skill.created","skill.validated","skill.published"]
    assert all(e["actor"] for e in events["events"])

def test_registry_versions_are_independent_and_listable(monkeypatch,tmp_path):
    use_db(monkeypatch,tmp_path); first=validate_skill_manifest(manifest()); skill_registry.create_draft(first)
    second=manifest(); second["metadata"]["version"]="1.1.0"; second["spec"]["instructions"]+=" Preserve all source spans."
    skill_registry.create_draft(validate_skill_manifest(second))
    result=skill_registry.list_versions(skill_id="date-arithmetic")
    assert result["count"]==2 and {v["version"] for v in result["versions"]}=={"1.0.0","1.1.0"}

def test_registry_rejects_mutation_and_deletion_of_immutable_versions(monkeypatch,tmp_path):
    use_db(monkeypatch,tmp_path); skill_registry.create_draft(validate_skill_manifest(manifest()))
    db=sqlite3.connect(tmp_path/"skills.sqlite3")
    with pytest.raises(sqlite3.IntegrityError,match="immutable"):
        db.execute("UPDATE skill_versions SET manifest_json='{}' WHERE skill_id='date-arithmetic'")
    db.rollback()
    with pytest.raises(sqlite3.IntegrityError,match="cannot be deleted"):
        db.execute("DELETE FROM skill_versions WHERE skill_id='date-arithmetic'")
    db.rollback(); db.close()

def test_registry_missing_version_is_explicit(monkeypatch,tmp_path):
    use_db(monkeypatch,tmp_path)
    with pytest.raises(skill_registry.SkillRegistryNotFound):
        skill_registry.get_version("unknown-skill","1.0.0")
