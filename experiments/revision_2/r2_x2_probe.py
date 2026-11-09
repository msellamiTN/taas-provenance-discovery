"""Revision 2, X2: runtime probing of the LiveMCPTool servers (review Major 1, Critical 1 and 4, Major 16).

Scope: the MCP reference servers of the LiveMCPBench configuration (data/raw/livemcpbench/all_config.json, commit
36a51a1) maintained by the modelcontextprotocol organisation (REFERENCE below). Third-party servers, in particular
those that execute shell commands or signal processes, are not probed in this environment (left to the authors, in
an isolated VM). Each server is started locally with its published launch command (npx / uvx; no credential is
configured; the filesystem server is rooted in the sandbox instead of "/"). Two phases:

inventory  start each server once, list its tools, record serverInfo and the live definitions, and compare them with
           the registry snapshot (tool present, description, input schema, annotations, definition hash h(t)).
probe      for every registry tool of a server that started: a fresh sandbox (HOME, working directory, TMPDIR) seeded
           with files, a git repository and office documents; the server is started under strace (-f), the tool is
           called once with arguments synthesised from its live input schema (paths inside the sandbox, URLs pointing
           at a local sink, commands "echo PAMCP_PROBE_EXEC", pids of a dummy process), and the system calls inside
           the call window are classified:
             write   successful open for writing, mkdir, rename or creation outside /dev, /proc, /sys and caches,
                     or a file created or modified in the sandbox (snapshot diff);
             delete  unlink / rmdir of a file that existed before the call, or a seed file missing after it;
             exec    execve during the call; "caller" when an argument contains the probe token, else "internal";
             network connect() to a non-loopback address, to the egress proxy, or a request on the local sink;
             read    open of a seed file for reading; session: a browser process started.
Observed effects establish presence, not absence: an effect that the probe did not trigger is "not observed".
Network access is limited by the environment's allowlist (most third-party APIs answer 403), so calls that need an API
usually fail after the connection attempt, which is still observed. Evidence class: OBSERVED (controlled execution).

Usage: python r2_x2_probe.py inventory | probe [--servers a,b] [--workers 3] | analyse
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "final"))

CONFIG = ROOT / "data" / "raw" / "livemcpbench" / "all_config.json"
OUT = ROOT / "results" / "revision_2"
REC = Path(os.environ.get("PAMCP_PROBE_RECORDS", str(ROOT / "data" / "x2_probe")))   # observation records
BOX = Path(os.environ.get("PAMCP_PROBE_DIR", str(Path(__import__("tempfile").gettempdir()) / "pamcp_probe_box")))
TOKEN = "PAMCP_PROBE_EXEC"
REFERENCE = ("filesystem", "git", "memory", "time", "sequential-thinking", "fetch")   # modelcontextprotocol/servers
START_TIMEOUT = float(os.environ.get("PAMCP_START_TIMEOUT", 240))
CALL_TIMEOUT = float(os.environ.get("PAMCP_CALL_TIMEOUT", 25))
_H = Path.home()   # package caches stay in the real home so that each sandbox does not re-download the servers
SHARED_CACHE = {"npm_config_cache": str(_H / ".npm"), "UV_CACHE_DIR": str(_H / ".cache" / "uv"),
                "UV_TOOL_DIR": str(_H / ".local" / "share" / "uv" / "tools"),
                "UV_PYTHON_INSTALL_DIR": str(_H / ".local" / "share" / "uv" / "python"),
                "PLAYWRIGHT_BROWSERS_PATH": str(_H / ".cache" / "ms-playwright"),
                "PUPPETEER_CACHE_DIR": str(_H / ".cache" / "puppeteer")}
NOISE = re.compile(r"(/_cacache/|/\.cache/uv/|__pycache__|\.pyc$|/\.npm/_logs/|/node-compile-cache|/\.npm/_update|"
                   r"/\.cache/node/|/v8-compile-cache|\.lock$|/\.local/share/uv/|/_npx/[^/]+/package-lock\.json$)")
SYS = ("/dev/", "/proc/", "/sys/", "/run/")
PROXY_PORT = int(re.sub(r".*:(\d+)/?$", r"\1", os.environ.get("HTTPS_PROXY", "http://127.0.0.1:0")) or 0)
STRACE = ["strace", "-f", "-ttt", "-qq", "-s", "160", "-e",
          "trace=execve,open,openat,creat,unlink,unlinkat,rename,renameat,renameat2,mkdir,mkdirat,rmdir,connect"]


# ------------------------------------------------------------------------------------------------ servers
def servers() -> dict[str, dict]:
    out = {}
    for e in json.loads(CONFIG.read_text()):
        for k, v in e["config"]["mcpServers"].items():
            args = [str(a) for a in v.get("args", [])]
            if k == "filesystem":
                args = [a if a != "/" else "{BOX}" for a in args]
            args = [a.replace("./annotated_data/files", "{BOX}/files") for a in args]
            out[k] = {"command": v.get("command"), "args": args, "env": v.get("env") or {}, "url": v.get("url")}
    return out


def registry() -> list[dict]:
    reg = json.loads((ROOT / "data" / "processed" / "registry_merged.json").read_text())["registry"]
    return [t for t in reg if t["source"] == "LiveMCPTool"]


def def_hash(server: str, t: dict) -> str:
    payload = json.dumps({"server": server, "name": t["name"], "description": t.get("description") or "",
                          "inputSchema": t.get("input_schema"), "outputSchema": t.get("output_schema"),
                          "annotations": t.get("annotations"), "extra": t.get("extra")},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _clean(d):
    if isinstance(d, dict):
        return {k: _clean(v) for k, v in d.items() if v is not None and k not in ("$schema",)}
    if isinstance(d, list):
        return [_clean(x) for x in d]
    return d


def live_dict(d: dict) -> dict:
    """Tool definition as published by the live server (raw JSON, no client-side validation)."""
    ann = d.get("annotations")
    return {"name": d["name"], "description": d.get("description") or "", "input_schema": d.get("inputSchema"),
            "output_schema": d.get("outputSchema"), "annotations": ann or None,
            "extra": {k: v for k, v in d.items() if k not in ("name", "description", "inputSchema", "outputSchema",
                                                                "annotations")} or None}


# ------------------------------------------------------------------------------------------------ sandbox
def seed(box: Path) -> dict:
    """Create the sandbox and its seed files; returns named paths used by argument synthesis."""
    if box.exists():
        shutil.rmtree(box, ignore_errors=True)
    for d in ("home", "work", "tmp", "files", "work/sub"):
        (box / d).mkdir(parents=True, exist_ok=True)
    w = box / "work"
    (w / "probe_in.txt").write_text("PAMCP_SEED line one\nline two\n")
    (w / "sub" / "probe_nested.txt").write_text("nested seed\n")
    (w / "probe.csv").write_text("id,value\n1,10\n2,20\n")
    (w / "probe.json").write_text('{"probe": 1}\n')
    (w / "probe.md").write_text("# Probe\n\ntext\n")
    (w / "probe.html").write_text("<html><body><h1>probe</h1><img src='probe.png'></body></html>")
    try:
        from PIL import Image
        Image.new("RGB", (8, 8), (200, 10, 10)).save(w / "probe.png")
    except Exception:
        pass
    try:
        import docx
        doc = docx.Document(); doc.add_heading("Probe", 0); doc.add_paragraph("PAMCP seed paragraph"); doc.save(w / "probe.docx")
    except Exception:
        pass
    try:
        import pptx
        p = pptx.Presentation(); s = p.slides.add_slide(p.slide_layouts[1]); s.shapes.title.text = "Probe"; p.save(w / "probe.pptx")
    except Exception:
        pass
    try:
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Sheet1"; ws.append(["id", "value"]); ws.append([1, 10])
        wb.save(w / "probe.xlsx")
    except Exception:
        pass
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(w / "probe.pdf")); c.drawString(72, 720, "PAMCP probe pdf"); c.save()
    except Exception:
        pass
    repo = w / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("probe repo\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@example.invalid",
           "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@example.invalid", "HOME": str(box / "home")}
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "."], ["git", "commit", "-q", "-m", "seed"]):
        subprocess.run(cmd, cwd=repo, env=env, check=False, capture_output=True)
    (repo / "README.md").write_text("probe repo\nuncommitted change\n")
    (repo / "staged.txt").write_text("staged change\n")
    subprocess.run(["git", "add", "staged.txt"], cwd=repo, env=env, check=False, capture_output=True)
    subprocess.run(["git", "branch", "probe-branch"], cwd=repo, env=env, check=False, capture_output=True)
    return {"box": box, "work": w, "file": w / "probe_in.txt", "dir": w, "repo": repo}


def snapshot(box: Path) -> dict[str, tuple]:
    out = {}
    for base in ("work", "home", "files", "tmp"):
        for p in (box / base).rglob("*"):
            if p.is_file() and "/.git/objects/" not in str(p) and not NOISE.search(str(p)):
                try:
                    st = p.stat()
                    out[str(p)] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    pass
    return out


# ------------------------------------------------------------------------------------------------ arguments
EXT = {"doc": "docx", "word": "docx", "ppt": "pptx", "presentation": "pptx", "slide": "pptx", "excel": "xlsx",
       "sheet": "xlsx", "workbook": "xlsx", "pdf": "pdf", "image": "png", "csv": "csv", "json": "json",
       "markdown": "md", "html": "html"}


def _ext_for(server: str, tool: str, key: str) -> str:
    s = f"{server} {tool} {key}".lower()
    for k, e in EXT.items():
        if k in s:
            return e
    return "txt"


def synth(schema: dict, key: str, server: str, tool: str, paths: dict, pid: int, sink: str, depth: int = 0):
    """Deterministic argument synthesis from a JSON schema and the parameter name."""
    schema = schema or {}
    if depth > 4:
        return None
    for alt in ("anyOf", "oneOf"):
        if alt in schema and schema[alt]:
            opts = [o for o in schema[alt] if o.get("type") != "null"] or schema[alt]
            return synth(opts[0], key, server, tool, paths, pid, sink, depth + 1)
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "string")
    k = key.lower()
    if t == "object" or ("properties" in schema and not t):
        props = schema.get("properties") or {}
        req = schema.get("required") or []
        return {p: synth(props.get(p, {}), p, server, tool, paths, pid, sink, depth + 1) for p in req if p in props} \
            if props else {}
    if t == "array":
        item = synth(schema.get("items") or {"type": "string"}, k.rstrip("s"), server, tool, paths, pid, sink, depth + 1)
        return [item]
    if t == "boolean":
        return False
    if t in ("integer", "number"):
        if "pid" in k:
            return pid
        lo = schema.get("minimum", schema.get("exclusiveMinimum", None))
        v = 1 if lo is None else (lo + 1 if "exclusiveMinimum" in schema else lo)
        hi = schema.get("maximum")
        if hi is not None and v > hi:
            v = hi
        return int(v) if t == "integer" else float(v)
    # strings
    w = paths["work"]
    ext = _ext_for(server, tool, k)
    if k in ("repo_path", "repository", "repo") or "repo" in k and "path" in k:
        return str(paths["repo"])
    if any(x in k for x in ("dir", "folder")) and "direction" not in k:
        return str(w)
    if any(x in k for x in ("output", "dest", "target", "new_", "save", "export")) and \
            any(x in k for x in ("path", "file", "name", "dir")):
        return str(w / f"probe_out.{ext}")
    if any(x in k for x in ("path", "file", "filename", "source", "src", "document", "presentation", "workbook")):
        cand = w / f"probe.{ext}"
        return str(cand if cand.exists() else paths["file"])
    if "url" in k or "uri" in k or "link" in k or "endpoint" in k or k in ("href", "website", "site"):
        return "https://example.com/pamcp-probe"        # public host (reference fetch refuses private addresses)
    if any(x in k for x in ("command", "cmd", "script", "shell")):
        return f"echo {TOKEN}"
    if k in ("code",) or "code" in k and "lang" not in k and "country" not in k and "zip" not in k:
        return f"print('{TOKEN}')"
    if "content" in k or "text" in k or "body" in k or "data" in k or "message" in k:
        return "PAMCP probe content"
    if "email" in k:
        return "probe@example.invalid"
    if "date" in k:
        return "2025-06-01"
    if "timezone" in k or k in ("tz", "zone"):
        return "Europe/Paris"
    if k == "time":
        return "12:00"
    if "time" in k:
        return "2025-06-01T12:00:00"
    if "symbol" in k or "ticker" in k:
        return "AAPL"
    if "lang" in k:
        return "en"
    if "color" in k or "colour" in k:
        return "#ff0000"
    if "sheet" in k:
        return "Sheet1"
    if "range" in k or "cell" in k:
        return "A1:B2"
    if "branch" in k:
        return "main"
    if "id" == k or k.endswith("_id") or k.endswith("id"):
        return "1"
    fmt = schema.get("format")
    if fmt == "uri":
        return f"{sink}/pamcp-probe"
    if fmt == "date":
        return "2025-06-01"
    return "PAMCP probe"


OVERRIDES = {   # per-server values that make a call semantically valid (documented in the result file)
    ("git", "files"): ["README.md"], ("git", "revision"): "HEAD", ("git", "target"): "HEAD",
    ("git", "branch_name"): "probe-branch", ("git", "branch_type"): "local", ("git", "base_branch"): "main",
}


def arguments(tool_live: dict, server: str, paths: dict, pid: int, sink: str, reg_schema: dict | None = None) -> dict:
    """Required arguments from the live schema; when the live schema publishes no properties (e.g. filesystem
    2025.8.18 sends {"$schema": ...} only), the registry snapshot's schema of the same tool is used instead."""
    sch = tool_live.get("input_schema") or {}
    if not (sch.get("properties")) and reg_schema:
        sch = reg_schema
    props = sch.get("properties") or {}
    req = list(sch.get("required") or [])
    args = {}
    for p in req:
        if (server, p) in OVERRIDES:
            args[p] = "probe-new" if p == "branch_name" and "create" in tool_live["name"] else OVERRIDES[(server, p)]
            continue
        v = synth(props.get(p, {}), p, server, tool_live["name"], paths, pid, sink)
        if server == "git" and isinstance(v, str) and v.startswith(str(paths["work"])) and p != "repo_path":
            v = "README.md"
        args[p] = v
    return args


# ------------------------------------------------------------------------------------------------ sink
class Sink:
    def __init__(self):
        self.hits: list[dict] = []
        sink = self

        class H(BaseHTTPRequestHandler):
            def _rec(self):
                n = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(n).decode(errors="replace")[:300] if n else ""
                sink.hits.append({"t": time.time(), "method": self.command, "path": self.path, "body": body})
                self.send_response(200); self.send_header("content-type", "text/plain"); self.end_headers()
                self.wfile.write(b"probe sink")
            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _rec

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"


# ------------------------------------------------------------------------------------------------ strace parsing
LINE = re.compile(r"^(\d+)\s+(\d+\.\d+)\s+(.*)$")


def parse_trace(path: Path) -> list[tuple[float, int, str]]:
    """Return (ts, pid, full syscall text) with unfinished/resumed pairs joined."""
    pend, out = {}, []
    if not path.exists():
        return out
    for raw in path.read_text(errors="replace").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        pid, ts, rest = int(m.group(1)), float(m.group(2)), m.group(3)
        if rest.endswith("<unfinished ...>"):
            pend[pid] = (ts, rest[: -len("<unfinished ...>")])
            continue
        r = re.match(r"<\.\.\. (\w+) resumed>(.*)", rest)
        if r:
            if pid in pend:
                ts0, head = pend.pop(pid)
                out.append((ts0, pid, head + r.group(2)))
            continue
        out.append((ts, pid, rest))
    return out


def classify(events, t0, t1, before: dict, after: dict, box: Path, sink_hits, proxy_port: int) -> dict:
    obs = {"write": [], "delete": [], "exec_caller": [], "exec_internal": [], "network": [], "read_seed": [],
           "session": []}
    seeds = set(before)
    for ts, pid, s in events:
        if ts < t0 - 0.05 or ts > t1:
            continue
        call = s.split("(", 1)[0]
        ok = not re.search(r"=\s*-1\s", s)
        if call == "execve":
            if not ok:
                continue
            argv = s[:400]
            (obs["exec_caller"] if TOKEN in s else obs["exec_internal"]).append(argv)
            if re.search(r"chrom|firefox|webkit|headless_shell", argv, re.I):
                obs["session"].append(argv)
        elif call in ("open", "openat", "creat"):
            m = re.search(r'"([^"]+)"', s)
            if not m or not ok:
                continue
            p = m.group(1)
            if p.startswith(SYS) or NOISE.search(p) or not p.startswith("/"):
                continue
            if call == "creat" or re.search(r"O_WRONLY|O_RDWR|O_CREAT|O_TRUNC|O_APPEND", s):
                obs["write"].append(p)
            elif p in seeds:
                obs["read_seed"].append(p)
        elif call in ("unlink", "unlinkat", "rmdir"):
            m = re.search(r'"([^"]+)"', s)
            if m and ok and not m.group(1).startswith(SYS) and not NOISE.search(m.group(1)):
                if m.group(1) in seeds or call == "rmdir" and m.group(1).startswith(str(box)):
                    obs["delete"].append(m.group(1))
        elif call in ("rename", "renameat", "renameat2", "mkdir", "mkdirat"):
            ms = re.findall(r'"([^"]+)"', s)
            if ms and ok and not ms[-1].startswith(SYS) and not NOISE.search(ms[-1]):
                obs["write"].append(ms[-1])
                if call.startswith("rename") and ms[0] in seeds:
                    obs["delete"].append(ms[0])
        elif call == "connect":
            if "AF_UNIX" in s or "AF_NETLINK" in s:
                continue
            m = re.search(r'sin6?_port=htons\((\d+)\).*?(?:inet_addr|inet_pton\(AF_INET6,)\s*\(?"([^"]+)"', s)
            if not m:
                continue
            port, addr = int(m.group(1)), m.group(2)
            loop = addr.startswith("127.") or addr in ("::1", "::ffff:127.0.0.1")
            if not loop or port == proxy_port or port == 53:
                obs["network"].append(f"{addr}:{port}")
    # snapshot diff inside the sandbox
    created = [p for p in after if p not in before]
    modified = [p for p in after if p in before and after[p] != before[p]]
    removed = [p for p in before if p not in after]
    obs["write"] += [p for p in created + modified]
    obs["delete"] += removed
    if sink_hits:
        obs["network"] += [f"sink:{h['method']} {h['path']}" for h in sink_hits]
    for k in obs:
        obs[k] = sorted(set(obs[k]))[:40]
    obs["snapshot"] = {"created": sorted(created)[:20], "modified": sorted(modified)[:20], "removed": sorted(removed)[:20]}
    return obs


# ------------------------------------------------------------------------------------------------ client
class Raw:
    """Minimal MCP client over stdio (JSON-RPC 2.0, newline-delimited). It does not validate the server's messages,
    so servers whose published schemas violate the specification (e.g. inputSchema without "type", which the Python
    SDK rejects) can still be listed and called; such violations are recorded by the inventory."""
    PROTOCOL = "2025-06-18"

    def __init__(self):
        self.proc = None
        self.next_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.reader_task = None
        self.stdout_noise = 0

    async def start(self, cmd: str, args: list[str], env: dict, cwd: str, errlog):
        self.proc = await asyncio.create_subprocess_exec(cmd, *args, stdin=asyncio.subprocess.PIPE,
                                                         stdout=asyncio.subprocess.PIPE, stderr=errlog, env=env,
                                                         cwd=cwd, start_new_session=True, limit=1 << 25)
        self.reader_task = asyncio.create_task(self._read())

    async def _read(self):
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except ValueError:
                self.stdout_noise += 1
                continue
            if not isinstance(msg, dict):
                continue
            if "method" in msg and "id" in msg:            # server -> client request
                m = msg["method"]
                if m in ("roots/list", "ping"):
                    body = {"jsonrpc": "2.0", "id": msg["id"], "result": {"roots": []} if m == "roots/list" else {}}
                else:
                    body = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "not supported"}}
                await self._send(body)
            elif "id" in msg and msg["id"] in self.pending:
                fut = self.pending.pop(msg["id"])
                if not fut.done():
                    fut.set_result(msg)
        for fut in self.pending.values():
            if not fut.done():
                fut.set_exception(EOFError("server closed stdout"))

    async def _send(self, body: dict):
        self.proc.stdin.write((json.dumps(body) + "\n").encode())
        await self.proc.stdin.drain()

    async def request(self, method: str, params: dict | None, timeout: float) -> dict:
        self.next_id += 1
        i = self.next_id
        fut = asyncio.get_running_loop().create_future()
        self.pending[i] = fut
        body = {"jsonrpc": "2.0", "id": i, "method": method}
        if params is not None:
            body["params"] = params
        await self._send(body)
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise RuntimeError(f"JSON-RPC error {msg['error'].get('code')}: {str(msg['error'].get('message'))[:200]}")
        return msg.get("result") or {}

    async def initialize(self, timeout: float) -> dict:
        r = await self.request("initialize", {"protocolVersion": self.PROTOCOL, "capabilities": {"roots": {}},
                                              "clientInfo": {"name": "pamcp-probe", "version": "0.2"}}, timeout)
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return r

    async def list_tools(self, timeout: float) -> list[dict]:
        tools, cursor = [], None
        for _ in range(20):
            r = await self.request("tools/list", {"cursor": cursor} if cursor else {}, timeout)
            tools += r.get("tools") or []
            cursor = r.get("nextCursor")
            if not cursor:
                break
        return tools

    async def close(self):
        if not self.proc:
            return
        try:
            self.proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            await asyncio.wait_for(self.proc.wait(), 2)
        except asyncio.TimeoutError:
            pass
        for sig in (15, 9):                                 # the whole process group (strace and the server)
            try:
                os.killpg(self.proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                await asyncio.wait_for(self.proc.wait(), 2)
                break
            except asyncio.TimeoutError:
                continue
        if self.reader_task:
            self.reader_task.cancel()


def server_cmd(name: str, cfg: dict, box: Path, traced: Path | None):
    args = [a.replace("{BOX}", str(box / "work" if name == "filesystem" else box)) for a in cfg["args"]]
    cmd = cfg["command"]
    env = {k: v for k, v in os.environ.items()}
    env.update(SHARED_CACHE)
    env.update({"HOME": str(box / "home"), "TMPDIR": str(box / "tmp"), "XDG_CONFIG_HOME": str(box / "home" / ".config"),
                "XDG_DATA_HOME": str(box / "home" / ".local" / "share"), "PYTHONDONTWRITEBYTECODE": "1",
                "NO_UPDATE_NOTIFIER": "1", "npm_config_update_notifier": "false"})
    env.update(cfg.get("env") or {})
    if traced is not None:
        return STRACE[0], STRACE[1:] + ["-o", str(traced), cmd, *args], env, str(box / "work")
    return cmd, args, env, str(box / "work")


def schema_violations(tools: list[dict]) -> list[str]:
    return [t.get("name", "?") for t in tools
            if not isinstance(t.get("inputSchema"), dict) or t["inputSchema"].get("type") != "object"]


async def inventory_one(name: str, cfg: dict) -> dict:
    box = BOX / f"inv_{re.sub(r'[^A-Za-z0-9_-]', '_', name)}"
    seed(box)
    rec = {"server": name, "command": cfg["command"], "args": cfg["args"], "started": False}
    if cfg.get("url") or not cfg.get("command"):
        rec["error"] = "remote server (url)"
        return rec
    errp = box / "stderr.log"
    t0 = time.time()
    c = Raw()
    try:
        with open(errp, "w") as err:
            await c.start(*server_cmd(name, cfg, box, None), errlog=err)
            init = await c.initialize(START_TIMEOUT)
            tools = await c.list_tools(60)
            rec["started"] = True
            rec["start_s"] = time.time() - t0
            rec["server_info"] = init.get("serverInfo")
            rec["protocol"] = init.get("protocolVersion")
            rec["tools"] = [live_dict(t) for t in tools]
            rec["schema_violations"] = schema_violations(tools)
            rec["stdout_noise_lines"] = c.stdout_noise
    except BaseException as e:  # noqa: BLE001  (record any startup failure)
        rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        if isinstance(e, KeyboardInterrupt):
            raise
    finally:
        await c.close()
    if not rec["started"]:
        rec["stderr_tail"] = errp.read_text(errors="replace")[-600:] if errp.exists() else ""
    shutil.rmtree(box, ignore_errors=True)
    print("inventory", name, rec["started"], len(rec.get("tools", [])), rec.get("error", "")[:80], flush=True)
    return rec


def inventory(only: set[str] | None = None) -> None:
    REC.mkdir(parents=True, exist_ok=True)
    path = REC / "inventory.json"
    inv = json.loads(path.read_text()) if path.exists() else {}
    for name, cfg in servers().items():
        if name not in (only or REFERENCE) or name not in REFERENCE:
            continue
        if name in inv and inv[name].get("started") and not only:
            continue
        inv[name] = asyncio.run(inventory_one(name, cfg))
        path.write_text(json.dumps(inv, indent=1, sort_keys=True))


async def probe_one(name: str, cfg: dict, tool_live: dict, idx: int, sink: Sink, reg_schema: dict | None = None) -> dict:
    box = BOX / f"p{idx:04d}"
    paths = seed(box)
    dummy = subprocess.Popen(["sleep", "300"], cwd=str(box / "work"))
    args = arguments(tool_live, name, paths, dummy.pid, sink.url, reg_schema)
    trace = box / "trace.txt"
    rec = {"server": name, "tool": tool_live["name"], "id": f"{name}::{tool_live['name']}", "args": args,
           "status": "not_started"}
    errp = box / "stderr.log"
    t0 = t1 = t1e = time.time()
    before, after, hits = {}, {}, []
    c = Raw()
    try:
        with open(errp, "w") as err:
            await c.start(*server_cmd(name, cfg, box, trace), errlog=err)
            await c.initialize(START_TIMEOUT)
            await c.list_tools(60)
            before = snapshot(box)
            hits0 = len(sink.hits)
            t0 = time.time()
            rec["status"] = "called"
            try:
                res = await c.request("tools/call", {"name": tool_live["name"], "arguments": args}, CALL_TIMEOUT)
                rec["is_error"] = bool(res.get("isError"))
                txt = " ".join(x.get("text", "") for x in res.get("content") or [] if isinstance(x, dict))
                rec["result_head"] = txt[:400]
                rec["status"] = "error_result" if rec["is_error"] else "ok"
            except asyncio.TimeoutError:
                rec["status"] = "timeout"
            except Exception as e:  # noqa: BLE001
                rec["status"] = "rpc_error" if isinstance(e, RuntimeError) else "exception"
                rec["exception"] = f"{type(e).__name__}: {str(e)[:300]}"
            t1 = time.time()
            await asyncio.sleep(0.6)
            t1e = time.time()
            after = snapshot(box)
            hits = [h for h in sink.hits[hits0:] if t0 - 0.05 <= h["t"] <= t1e]
    except BaseException as e:  # noqa: BLE001
        if rec["status"] == "not_started":
            rec["start_error"] = f"{type(e).__name__}: {str(e)[:300]}"
        if isinstance(e, KeyboardInterrupt):
            raise
    finally:
        await c.close()
        dummy.kill()
    if rec["status"] == "not_started":
        rec["stderr_tail"] = errp.read_text(errors="replace")[-400:] if errp.exists() else ""
    else:
        await asyncio.sleep(0.2)
        events = parse_trace(trace)
        rec["observed"] = classify(events, t0, t1e, before, after, box, hits, PROXY_PORT)
        rec["call_s"] = t1 - t0
    shutil.rmtree(box, ignore_errors=True)
    o = rec.get("observed", {})
    print(f"probe {idx} {rec['id'][:60]:60s} {rec['status']:12s} "
          + " ".join(f"{k}={len(v)}" for k, v in o.items() if isinstance(v, list) and v), flush=True)
    return rec


async def probe_all(only: set[str] | None, workers: int) -> None:
    inv = json.loads((REC / "inventory.json").read_text())
    reg = registry()
    reg_ids = {t["id"] for t in reg}
    reg_schema_of = {t["id"]: t.get("input_schema") for t in reg}
    out_p = REC / "probes.jsonl"
    done = set()
    if out_p.exists() and "--redo" not in sys.argv:
        done = {json.loads(x)["id"] for x in out_p.read_text().splitlines() if x.strip()}
    jobs = []
    cfgs = servers()
    for name in sorted(inv):
        if name not in REFERENCE or only and name not in only or not inv[name].get("started"):
            continue
        for t in inv[name]["tools"]:
            tid = f"{name}::{t['name']}"
            if tid in reg_ids and tid not in done:
                jobs.append((name, cfgs[name], t, reg_schema_of.get(tid)))
    print("probe jobs", len(jobs), flush=True)
    sink = Sink()
    sem = asyncio.Semaphore(workers)
    lock = asyncio.Lock()

    async def run(i, job):
        async with sem:
            rec = await probe_one(*job[:3], idx=i, sink=sink, reg_schema=job[3])
            async with lock:
                with open(out_p, "a") as f:
                    f.write(json.dumps(rec, sort_keys=True) + "\n")

    # one job per server at a time keeps per-server state (shared npx package dir) from interleaving
    by_server: dict[str, list] = {}
    for i, j in enumerate(jobs):
        by_server.setdefault(j[0], []).append((i, j))

    async def server_chain(items):
        for i, j in items:
            await run(i, j)

    await asyncio.gather(*(server_chain(v) for v in by_server.values()))


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    only = None
    if "--servers" in sys.argv:
        only = set(sys.argv[sys.argv.index("--servers") + 1].split(","))
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    BOX.mkdir(parents=True, exist_ok=True)
    if mode == "inventory":
        inventory(only)
    elif mode == "probe":
        asyncio.run(probe_all(only, workers))
    elif mode == "analyse":
        import r2_x2_analyse
        r2_x2_analyse.main()


if __name__ == "__main__":
    main()
