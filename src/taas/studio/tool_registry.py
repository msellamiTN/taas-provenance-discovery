"""Tool Intelligence v1.1 — Registry Resolver and Capability Intelligence Profile.

Resolves exact tool identities from the repository-retained registry snapshot,
verifies stored definition hashes, and extracts structured capability profiles
with an explicit evidence-kind axis:

  * ``declared``   — publisher-supplied schemas/annotations (metadata, not trusted)
  * ``observed``   — obs records in a Core EvidenceStore (wired only when supplied)
  * ``attested``   — verified assurance-evidence records bound to (tool, h(tool))

Contract extraction runs through ``taas.contracts.extract_contract``; when an
``EvidenceStore`` is supplied its obs/att records upgrade the contract's
evidence kind exactly as Core intends — nothing invents stronger evidence.
Registry resolution is browsing with identity, not discovery, authorization or
execution.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, Mapping

from taas.contracts import extract_contract
from taas.data.registries import RawTool, load_processed, raw_tools_from_processed
from taas.provenance import EvidenceStore

RESOLVER_SCHEMA = "taas.tool-identity/v1"
PROFILE_SCHEMA = "taas.tool-capability-profile/v1"
_EVIDENCE_ORDER = ("lex", "ann", "obs", "att")


@lru_cache(maxsize=1)
def _raw_tools() -> dict[str, RawTool]:
    return {t.id: t for t in raw_tools_from_processed(load_processed())}


@lru_cache(maxsize=1)
def _registry_entries() -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in load_processed().get("registry", [])}


def search_registry_tools(
    *,
    q: str | None = None,
    server: str | None = None,
    source: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Filter retained-registry identities; annotations stay untrusted metadata."""
    entries = sorted(_registry_entries().values(), key=lambda item: str(item.get("id")))
    if server is not None:
        entries = [e for e in entries if e.get("server") == server]
    if source is not None:
        entries = [e for e in entries if e.get("source") == source]
    if q:
        needle = q.casefold()
        entries = [e for e in entries if needle in " ".join((
            str(e.get("server", "")), str(e.get("name", "")), str(e.get("description", "")),
        )).casefold()]
    page = entries[offset:offset + limit]
    return {
        "schema": RESOLVER_SCHEMA,
        "total": len(entries),
        "offset": offset,
        "limit": limit,
        "tools": [
            {
                "tool_id": e.get("id"),
                "server": e.get("server"),
                "name": e.get("name"),
                "source": e.get("source"),
                "category": e.get("category"),
                "definition_hash": e.get("hash"),
                "annotations_present": bool(e.get("annotations")),
            }
            for e in page
        ],
        "registry_source": "repository-retained snapshot",
        "annotations_are_trusted_evidence": False,
    }


def resolve_registry_tool(server: str, name: str) -> dict[str, Any] | None:
    """Resolve one exact ``server::name`` identity with definition-hash verification."""
    tool_id = f"{server}::{name}"
    entry = _registry_entries().get(tool_id)
    raw = _raw_tools().get(tool_id)
    if entry is None or raw is None:
        return None
    recomputed = raw.definition_hash()
    stored = entry.get("hash")
    return {
        "schema": RESOLVER_SCHEMA,
        "tool_id": tool_id,
        "server": server,
        "name": name,
        "description": raw.description,
        "source": entry.get("source"),
        "category": entry.get("category"),
        "definition_hash": stored,
        "definition_hash_recomputed": recomputed,
        "definition_hash_verified": stored == recomputed,
        "registry_source": "repository-retained snapshot",
        "annotations_are_trusted_evidence": False,
    }


def build_capability_profile(
    server: str,
    name: str,
    *,
    evidence_store: EvidenceStore | None = None,
    attestation_lookup: Any = None,
) -> dict[str, Any] | None:
    """Extract the structured capability profile for one exact registry tool.

    ``attestation_lookup`` is a callable ``(binding) -> {"count": int, ...}``;
    the caller wires it to verified assurance evidence. Absent lookups are
    reported as ``unavailable``, never as zero verified records.
    """
    tool_id = f"{server}::{name}"
    identity = resolve_registry_tool(server, name)
    raw = _raw_tools().get(tool_id)
    if identity is None or raw is None:
        return None

    contract = extract_contract(raw, store=evidence_store)
    stored_props = evidence_store.get(raw.id, contract.h) if evidence_store else {}
    observed = evidence_store.effects(raw.id, contract.h) if evidence_store else None
    evidence_kind = contract.eff_record.ptype

    binding = {"tool_id": tool_id, "definition_hash": contract.h}
    attested: dict[str, Any] = {"status": "lookup_not_configured", "verified_records": None}
    if attestation_lookup is not None:
        try:
            found = attestation_lookup(binding)
            attested = {"status": "performed",
                        "verified_records": int(found.get("count", len(found.get("valid", [])))),
                        "invalid_records": len(found.get("invalid", []))}
        except Exception as exc:
            attested = {"status": "lookup_failed", "error": f"{type(exc).__name__}", "verified_records": None}

    return {
        "schema": PROFILE_SCHEMA,
        "identity": identity,
        "capability": {
            "tool_class": contract.tool_class,
            "output_type": str(contract.out.type),
            "output_type_confidence": contract.out.confidence,
            "output_type_assigned_by": contract.out.source,
            "inputs": [
                {
                    "argument": arg.name,
                    "type": str(arg.type),
                    "required": arg.required,
                    "confidence": arg.confidence,
                }
                for arg in contract.args
            ],
            "required_credentials": list(contract.req),
            "information_source_label": contract.flow.source_label,
            "tokens_estimate": contract.tokens,
            "qos": {
                "price": contract.qos.price,
                "latency": contract.qos.latency,
                "failure_probability": contract.qos.fail,
            },
        },
        "effects": {
            "declared_effects": sorted(str(e) for e in contract.eff),
            "evidence_kind": evidence_kind,
            "evidence_method": contract.eff_record.method,
        },
        "evidence_summary": {
            "contract_evidence_kind": evidence_kind,
            "strongest_kind_available": evidence_kind,
            "declared": {
                "input_schema_present": bool(raw.input_schema),
                "output_schema_present": raw.output_schema is not None,
                "annotations_present": bool(raw.annotations),
                "annotations_are_trusted_evidence": False,
            },
            "observed": {
                "evidence_store_wired": evidence_store is not None,
                "stored_property_records": sum(len(v) for v in stored_props.values()),
                "observed_effects_present": observed is not None,
            },
            "attested": attested,
        },
        "provenance": {
            "source": identity.get("source"),
            "category": identity.get("category"),
            "contract_fingerprint": contract.h,
            "registry_snapshot_source": "repository-retained snapshot",
        },
        "structural_profile_only": True,
        "semantic_correctness_verified": False,
        "tool_invoked": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }


def reset_registry_caches() -> None:
    """Test hook: clear the process-cached snapshot views."""
    _raw_tools.cache_clear()
    _registry_entries.cache_clear()
