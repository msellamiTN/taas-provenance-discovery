"""Loading the public MCP registries of Table 1 and their task sets.

* LiveMCPTool (LiveMCPBench, Apache-2.0): 69 servers, 525 tools, 95 annotated tasks.
* MCPToolBench++ (MIT): 10 servers, 87 tools, single-call requests in 6 categories.
* Merged registry: tools identified by ``server::name`` → 76 servers, 569 tools.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


@dataclass
class RawTool:
    """A tool definition as published by an MCP server (tools/list)."""

    server: str
    name: str
    description: str
    input_schema: dict
    output_schema: dict | None = None
    annotations: dict | None = None
    source: str = ""
    category: str = ""

    @property
    def id(self) -> str:
        return f"{self.server}::{self.name}"

    extra: dict | None = None  # any further published fields (title, _meta, extensions)

    def definition_hash(self) -> str:
        """h(t): SHA-256 over the canonical JSON of the whole published definition (server, name,
        description, schemas, annotations and any extra fields), kept at 128 bits."""
        payload = json.dumps(
            {"server": self.server, "name": self.name, "description": self.description,
             "inputSchema": self.input_schema, "outputSchema": self.output_schema,
             "annotations": self.annotations, "extra": self.extra},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:32]


@dataclass
class Task:
    """A benchmark request with its gold tools (server::name ids when resolvable)."""

    id: str
    query: str
    source: str
    category: str
    gold_tools: list[str] = field(default_factory=list)
    gold_unresolved: list[str] = field(default_factory=list)
    n_steps: int = 1


def load_livemcptool(raw: Path = RAW) -> list[RawTool]:
    data = json.load(open(raw / "livemcpbench" / "tools.json"))
    out = []
    for s in data:
        for key, v in s["tools"].items():
            for t in v["tools"]:
                out.append(RawTool(key, t["name"], t.get("description") or "", t.get("inputSchema") or {},
                                   t.get("outputSchema"), t.get("annotations"), "LiveMCPTool",
                                   s.get("category", "")))
    return out


def _pp_files(raw: Path) -> list[Path]:
    """Return MCPToolBench++ category JSON files; fail clearly when absent."""
    directory = Path(raw) / "mcptoolbenchpp"
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    if not files:
        raise FileNotFoundError(
            "MCPToolBench++ raw category JSON files are missing. "
            f"Expected six pinned category files under {directory}. "
            "Restore them with: python scripts/fetch_mcptoolbenchpp.py"
        )
    return files


def load_mcptoolbenchpp(raw: Path = RAW) -> tuple[list[RawTool], list[Task]]:
    tools: dict[str, RawTool] = {}
    tasks: list[Task] = []
    for f in _pp_files(raw):
        cat = f.stem
        with f.open(encoding="utf-8") as stream:
            rows = json.load(stream)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"MCPToolBench++ category file is empty or not a JSON list: {f}")
        for row_index, r in enumerate(rows):
            required = {"uuid", "query", "tools", "function_call_label"}
            missing = sorted(required - set(r))
            if missing:
                raise ValueError(
                    f"Malformed MCPToolBench++ row {row_index} in {f.name}; missing fields: {missing}"
                )
            srv = {n: s for s, names in r.get("mcp_tools_dict", {}).items() for n in names}
            for t in r["tools"]:
                rt = RawTool(srv.get(t["name"], "unknown"), t["name"], (t.get("description") or "").strip(),
                             t.get("input_schema") or t.get("inputSchema") or {}, None, None,
                             "MCPToolBench++", cat)
                tools.setdefault(rt.id, rt)
            gold = [f"{c.get('mcp_server') or srv.get(c['name'], 'unknown')}::{c['name']}"
                    for c in r["function_call_label"]]
            tasks.append(Task(r["uuid"], r["query"], "MCPToolBench++", cat, gold, [],
                              len(r["function_call_label"])))
    if not tools or not tasks:
        raise ValueError(
            f"MCPToolBench++ files were found under {Path(raw) / 'mcptoolbenchpp'} "
            f"but produced tools={len(tools)} and tasks={len(tasks)}."
        )
    return list(tools.values()), tasks


def merge_registries(*regs: list[RawTool]) -> list[RawTool]:
    """Merge by server::name (first occurrence wins; LiveMCPTool first)."""
    seen: dict[str, RawTool] = {}
    for reg in regs:
        for t in reg:
            seen.setdefault(t.id, t)
    return list(seen.values())


def load_livemcpbench_tasks(registry: list[RawTool], raw: Path = RAW) -> list[Task]:
    by_name: dict[str, list[str]] = {}
    for t in registry:
        by_name.setdefault(t.name, []).append(t.id)
    tasks = []
    for q in json.load(open(raw / "livemcpbench" / "all_annotations.json")):
        meta = q["Annotator Metadata"]
        names = [re.sub(r"^\d+\.\s*", "", l).strip().strip("`") for l in meta["Tools"].split("\n") if l.strip()]
        gold, unres = [], []
        for n in names:
            ids = [i for i in by_name.get(n, []) if not i.startswith(("puppeteer::", "playwright::"))] \
                or by_name.get(n, [])
            if ids:
                # ambiguous names (e.g. read_file on several servers) keep every candidate id
                gold.append(ids[0] if len(ids) == 1 else "|".join(sorted(ids)))
            else:
                unres.append(n)
        try:
            nsteps = int(meta.get("Number of steps") or len(names))
        except ValueError:
            nsteps = len(names)
        tasks.append(Task(q["task_id"], q["Question"], "LiveMCPBench", q["category"], gold, unres, nsteps))
    return tasks


def registry_stats(registry: list[RawTool]) -> dict:
    servers = {t.server for t in registry}
    ann = [t for t in registry if t.annotations]
    return {
        "servers": len(servers), "tools": len(registry), "annotated": len(ann),
        "annotated_servers": sorted({t.server for t in ann}),
        "annotated_read_only_true": sum(1 for t in ann if (t.annotations or {}).get("readOnlyHint") is True),
        "by_source": dict(Counter(t.source for t in registry)),
    }


def build_all(write: bool = True) -> dict:
    live = load_livemcptool()
    pp_tools, pp_tasks = load_mcptoolbenchpp()
    merged = merge_registries(live, pp_tools)
    live_tasks = load_livemcpbench_tasks(merged)
    out = {
        "registry": [asdict(t) | {"id": t.id, "hash": t.definition_hash()} for t in merged],
        "tasks_livemcpbench": [asdict(t) for t in live_tasks],
        "tasks_mcptoolbenchpp": [asdict(t) for t in pp_tasks],
        "stats": {
            "LiveMCPTool": registry_stats(live), "MCPToolBench++": registry_stats(pp_tools),
            "merged": registry_stats(merged),
            "requests": {"LiveMCPBench": len(live_tasks), "MCPToolBench++": len(pp_tasks),
                         "MCPToolBench++_unique_queries": len({t.query for t in pp_tasks})},
        },
    }
    if write:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        json.dump(out, open(PROCESSED / "registry_merged.json", "w"), indent=1, ensure_ascii=False)
    return out


def load_processed() -> dict:
    p = PROCESSED / "registry_merged.json"
    if not p.exists():
        return build_all(write=True)
    return json.load(open(p))


def raw_tools_from_processed(d: dict) -> list[RawTool]:
    keys = RawTool.__dataclass_fields__.keys()
    return [RawTool(**{k: r[k] for k in keys}) for r in d["registry"]]


def tasks_from_processed(d: dict, which: str) -> list[Task]:
    keys = Task.__dataclass_fields__.keys()
    return [Task(**{k: r[k] for k in keys}) for r in d[f"tasks_{which}"]]


if __name__ == "__main__":  # pragma: no cover
    res = build_all()
    print(json.dumps(res["stats"], indent=1))
    os.makedirs(PROCESSED, exist_ok=True)
