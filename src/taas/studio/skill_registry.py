"""SQLite-backed immutable Skill versions and append-only lifecycle events.

The registry stores reusable planning guidance. It does not grant tools,
permissions, data access, or execution rights.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class SkillRegistryError(RuntimeError):
    pass
class SkillRegistryConflict(SkillRegistryError):
    pass
class SkillRegistryNotFound(SkillRegistryError):
    pass

def _database_path() -> Path:
    configured = os.environ.get("TAAS_SKILL_REGISTRY_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".taas" / "studio" / "skills.sqlite3").resolve()

def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS skill_versions (
        skill_id TEXT NOT NULL, version TEXT NOT NULL, manifest_json TEXT NOT NULL,
        manifest_sha256 TEXT NOT NULL,
        lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('draft','validated','published')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (skill_id, version))""")
    db.execute("""CREATE TABLE IF NOT EXISTS skill_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, skill_id TEXT NOT NULL, version TEXT NOT NULL,
        event_type TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
        manifest_sha256 TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TEXT NOT NULL,
        FOREIGN KEY (skill_id, version) REFERENCES skill_versions(skill_id, version))""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_versions_immutable_fields
        BEFORE UPDATE OF skill_id, version, manifest_json, manifest_sha256, created_at
        ON skill_versions BEGIN SELECT RAISE(ABORT, 'Skill version content is immutable'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_versions_no_delete
        BEFORE DELETE ON skill_versions BEGIN SELECT RAISE(ABORT, 'Skill versions cannot be deleted'); END""")
    # Lifecycle columns are protected at the engine level, not only by the
    # transition() application path: direct SQL cannot bypass transition rules,
    # skip the append-only event record, or silently move updated_at.
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_versions_valid_transition
        BEFORE UPDATE OF lifecycle_state ON skill_versions
        WHEN NOT (
            OLD.lifecycle_state = NEW.lifecycle_state
            OR (OLD.lifecycle_state = 'draft' AND NEW.lifecycle_state = 'validated')
            OR (OLD.lifecycle_state = 'validated' AND NEW.lifecycle_state = 'published')
        )
        BEGIN SELECT RAISE(ABORT, 'Invalid Skill lifecycle transition'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_versions_state_requires_event
        AFTER UPDATE OF lifecycle_state ON skill_versions
        WHEN OLD.lifecycle_state <> NEW.lifecycle_state
        BEGIN
            SELECT RAISE(ABORT, 'Skill lifecycle change requires a recorded event')
            WHERE NOT EXISTS (
                SELECT 1 FROM skill_events
                WHERE skill_id = NEW.skill_id AND version = NEW.version
                  AND from_state = OLD.lifecycle_state
                  AND to_state = NEW.lifecycle_state
                  AND manifest_sha256 = NEW.manifest_sha256
                  AND occurred_at = NEW.updated_at
            );
        END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_versions_updated_at_guard
        BEFORE UPDATE OF updated_at ON skill_versions
        WHEN OLD.lifecycle_state = NEW.lifecycle_state
        BEGIN SELECT RAISE(ABORT, 'Skill updated_at may only change with a lifecycle transition'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_events_no_update
        BEFORE UPDATE ON skill_events BEGIN SELECT RAISE(ABORT, 'Skill lifecycle events are append-only'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_events_no_delete
        BEFORE DELETE ON skill_events BEGIN SELECT RAISE(ABORT, 'Skill lifecycle events are append-only'); END""")
    db.execute("""CREATE TABLE IF NOT EXISTS skill_revocations (
        skill_id TEXT NOT NULL, version TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
        revoked_by TEXT NOT NULL, reason TEXT NOT NULL, occurred_at TEXT NOT NULL,
        PRIMARY KEY (skill_id, version),
        FOREIGN KEY (skill_id, version) REFERENCES skill_versions(skill_id, version))""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_revocations_no_update
        BEFORE UPDATE ON skill_revocations BEGIN SELECT RAISE(ABORT, 'Skill revocations are immutable'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS skill_revocations_no_delete
        BEFORE DELETE ON skill_revocations BEGIN SELECT RAISE(ABORT, 'Skill revocations are immutable'); END""")
    if os.name == "posix":
        try:
            os.chmod(path.parent, 0o700); os.chmod(path, 0o600)
        except OSError:
            pass
    return db

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _canonical(manifest: dict[str, Any]) -> tuple[str, str]:
    body = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return body, hashlib.sha256(body.encode("utf-8")).hexdigest()

def _event(db: sqlite3.Connection, *, skill_id: str, version: str, event_type: str,
           from_state: str | None, to_state: str, digest: str, actor: str, occurred_at: str) -> None:
    db.execute("""INSERT INTO skill_events
        (skill_id,version,event_type,from_state,to_state,manifest_sha256,actor,occurred_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (skill_id,version,event_type,from_state,to_state,digest,actor,occurred_at))

def create_draft(manifest: dict[str, Any], actor: str = "studio-api") -> dict[str, Any]:
    skill_id, version = manifest["metadata"]["id"], manifest["metadata"]["version"]
    serialized, digest = _canonical(manifest); now = _now(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("""INSERT INTO skill_versions
                (skill_id,version,manifest_json,manifest_sha256,lifecycle_state,created_at,updated_at)
                VALUES (?,?,?,?, 'draft',?,?)""", (skill_id,version,serialized,digest,now,now))
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise SkillRegistryConflict(f"Skill version {skill_id}@{version} already exists; versions are immutable") from exc
        _event(db,skill_id=skill_id,version=version,event_type="skill.created",from_state=None,
               to_state="draft",digest=digest,actor=actor,occurred_at=now)
        db.commit()
    finally:
        db.close()
    return get_version(skill_id,version)

def is_revoked(skill_id: str, version: str) -> bool:
    db = _connect()
    try:
        row = db.execute(
            "SELECT 1 FROM skill_revocations WHERE skill_id=? AND version=?",
            (skill_id, version),
        ).fetchone()
    finally:
        db.close()
    return row is not None


def get_revocation(skill_id: str, version: str) -> dict[str, Any] | None:
    db = _connect()
    try:
        row = db.execute(
            "SELECT skill_id,version,manifest_sha256,revoked_by,reason,occurred_at "
            "FROM skill_revocations WHERE skill_id=? AND version=?",
            (skill_id, version),
        ).fetchone()
    finally:
        db.close()
    return dict(row) if row is not None else None


def revoke_version(skill_id: str, version: str, *, reason: str,
                   actor: str = "studio-api") -> dict[str, Any]:
    """Record an immutable revocation for a Skill version.

    Revocation never deletes or mutates the Skill version; it marks it unfit
    for new bindings. Existing immutable references remain inspectable.
    """
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise SkillRegistryConflict("Revocation reason must be 1-500 characters")
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT lifecycle_state,manifest_sha256 FROM skill_versions "
                         "WHERE skill_id=? AND version=?", (skill_id, version)).fetchone()
        if row is None:
            db.rollback()
            raise SkillRegistryNotFound(f"Skill version {skill_id}@{version} was not found")
        if row["lifecycle_state"] == "draft":
            db.rollback()
            raise SkillRegistryConflict("Draft Skill versions cannot be revoked")
        now = _now()
        try:
            db.execute("""INSERT INTO skill_revocations
                (skill_id,version,manifest_sha256,revoked_by,reason,occurred_at)
                VALUES (?,?,?,?,?,?)""",
                (skill_id, version, row["manifest_sha256"], actor, reason.strip(), now))
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise SkillRegistryConflict(f"Skill version {skill_id}@{version} is already revoked") from exc
        _event(db, skill_id=skill_id, version=version, event_type="skill.revoked",
               from_state=row["lifecycle_state"], to_state="revoked",
               digest=row["manifest_sha256"], actor=actor, occurred_at=now)
        db.commit()
    finally:
        db.close()
    return get_revocation(skill_id, version)


def get_version(skill_id: str, version: str) -> dict[str, Any]:
    db=_connect()
    try:
        row=db.execute("SELECT * FROM skill_versions WHERE skill_id=? AND version=?",(skill_id,version)).fetchone()
    finally:
        db.close()
    if row is None: raise SkillRegistryNotFound(f"Skill version {skill_id}@{version} was not found")
    return {"skill_id":row["skill_id"],"version":row["version"],"manifest":json.loads(row["manifest_json"]),
            "manifest_sha256":row["manifest_sha256"],"lifecycle_state":row["lifecycle_state"],
            "revoked": is_revoked(skill_id, version),
            "created_at":row["created_at"],"updated_at":row["updated_at"]}

def list_versions(skill_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    db=_connect()
    try:
        if skill_id is None:
            rows=db.execute("""SELECT skill_id,version,manifest_sha256,lifecycle_state,created_at,updated_at
                FROM skill_versions ORDER BY created_at DESC,skill_id,version LIMIT ?""",(limit,)).fetchall()
        else:
            rows=db.execute("""SELECT skill_id,version,manifest_sha256,lifecycle_state,created_at,updated_at
                FROM skill_versions WHERE skill_id=? ORDER BY created_at DESC,version LIMIT ?""",(skill_id,limit)).fetchall()
    finally: db.close()
    versions = [{**dict(row), "revoked": is_revoked(row["skill_id"], row["version"])} for row in rows]
    return {"count":len(versions),"versions":versions,"persistence":"sqlite","tenant_isolation":False}

def transition(skill_id: str, version: str, target_state: str, actor: str = "studio-api") -> dict[str, Any]:
    allowed={"draft":"validated","validated":"published"}
    if target_state not in {"validated","published"}:
        raise SkillRegistryConflict(f"Unsupported target lifecycle state: {target_state}")
    db=_connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM skill_versions WHERE skill_id=? AND version=?",(skill_id,version)).fetchone()
        if row is None:
            db.rollback(); raise SkillRegistryNotFound(f"Skill version {skill_id}@{version} was not found")
        current=row["lifecycle_state"]
        if allowed.get(current)!=target_state:
            db.rollback(); raise SkillRegistryConflict(f"Invalid Skill lifecycle transition {current} -> {target_state}")
        now=_now()
        # Event recorded before the state update: the AFTER-trigger verifies the
        # matching event exists inside this transaction. An aborted UPDATE rolls
        # back both — state and history stay atomic.
        _event(db,skill_id=skill_id,version=version,event_type=f"skill.{target_state}",from_state=current,
               to_state=target_state,digest=row["manifest_sha256"],actor=actor,occurred_at=now)
        db.execute("UPDATE skill_versions SET lifecycle_state=?,updated_at=? WHERE skill_id=? AND version=?",
                   (target_state,now,skill_id,version))
        db.commit()
    finally: db.close()
    return get_version(skill_id,version)

def list_events(skill_id: str | None = None, limit: int = 200) -> dict[str, Any]:
    db=_connect()
    try:
        if skill_id is None:
            rows=db.execute("SELECT * FROM skill_events ORDER BY event_id DESC LIMIT ?",(limit,)).fetchall()
        else:
            rows=db.execute("SELECT * FROM skill_events WHERE skill_id=? ORDER BY event_id DESC LIMIT ?",(skill_id,limit)).fetchall()
    finally: db.close()
    return {"count":len(rows),"events":[dict(row) for row in rows]}
