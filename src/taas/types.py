"""Semantic types Θ, subtyping <: and the typing function τ (paper, Section 5).

A semantic type is written ``kind[:domain][[]]``:

* ``kind``   one of the ontology kinds of the paper (record, document, text, table,
  media, credential, identifier, location) extended with the structural kinds
  needed by real MCP schemas (number, url, path, query, code, datetime, boolean,
  none).
* ``domain`` an optional registry domain term (``review``, ``stock``, ``repo``...).
* ``[]``     a collection of the element type.

Subtyping ``<:`` combines structural subtyping with the ontology:
``kind:domain <: kind``; ``T <: T``; ``T[] <: T[]`` iff element types are subtypes;
``record``/``table``/``document`` are *text-renderable* (a model edge may read
them) but are not subtypes of ``text``. A low-confidence type (κ < κ_min) is
``uncertain`` and never treated as an exact match (Section 6.3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

KINDS: tuple[str, ...] = (
    "text", "document", "table", "record", "media", "credential", "identifier",
    "location", "number", "url", "path", "query", "code", "datetime", "boolean", "none",
)
# kinds a language model can read from its context (used by checks (C) and σ validation)
TEXT_RENDERABLE: frozenset[str] = frozenset(
    {"text", "document", "table", "record", "identifier", "location", "number", "url",
     "path", "query", "code", "datetime", "boolean"}
)

_TYPE_RE = re.compile(r"^(?P<kind>[a-z_]+)(?::(?P<domain>[a-z0-9_\-]+))?(?P<coll>\[\])?$")


@dataclass(frozen=True, order=True)
class SemType:
    """A semantic data type θ ∈ Θ."""

    kind: str
    domain: str | None = None
    collection: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind {self.kind!r}")

    def __str__(self) -> str:
        s = self.kind if self.domain is None else f"{self.kind}:{self.domain}"
        return s + ("[]" if self.collection else "")

    @property
    def element(self) -> "SemType":
        return SemType(self.kind, self.domain, False)

    @property
    def is_text_renderable(self) -> bool:
        return self.kind in TEXT_RENDERABLE


@lru_cache(maxsize=65536)
def parse_type(s: str | SemType) -> SemType:
    """Parse ``kind[:domain][[]]``; unknown kinds degrade to ``text``."""
    if isinstance(s, SemType):
        return s
    s = (s or "none").strip().lower().replace(" ", "_")
    m = _TYPE_RE.match(s)
    if not m:
        return SemType("text")
    kind = m.group("kind")
    if kind not in KINDS:
        return SemType("text", kind)  # keep the unknown word as a domain term
    dom = m.group("domain")
    if dom is not None:
        dom = normalise_domain(dom)
    return SemType(kind, dom, bool(m.group("coll")))


_SYNONYMS = {
    "reviews": "review", "issues": "issue", "repos": "repo", "repository": "repo",
    "stocks": "stock", "quotes": "stock", "quote": "stock", "ticker": "stock",
    "webpage": "web", "html": "web", "page": "web", "website": "web",
    "spreadsheet": "sheet", "xlsx": "sheet", "excel": "sheet",
    "slides": "slide", "pptx": "slide", "presentation": "slide", "ppt": "slide",
    "docx": "word", "doc": "word", "messages": "message", "msg": "message",
    "search_results": "search_result", "results": "search_result", "result": "search_result",
    "papers": "paper", "articles": "article", "news_item": "news", "packages": "package",
    "images": "image", "picture": "image", "photo": "image", "charts": "chart",
    "graph": "chart", "plot": "chart", "places": "place", "poi": "place",
}


def normalise_domain(d: str) -> str:
    d = d.strip().lower().replace("-", "_")
    d = _SYNONYMS.get(d, d)
    if d.endswith("s") and len(d) > 4 and not d.endswith(("ss", "is", "us", "ics", "news")):
        d = _SYNONYMS.get(d[:-1], d[:-1])
    return d


def subtype(a: str | SemType, b: str | SemType) -> bool:
    """θa <: θb."""
    a, b = parse_type(a), parse_type(b)
    if b.kind == "none":
        return a.kind == "none"
    # ontology: a single-domain table is a collection of records
    if a.kind == "table" and not a.collection and b.kind == "record" and b.collection:
        return b.domain is None or a.domain == b.domain
    if a.collection != b.collection:
        return False
    if a.kind != b.kind:
        return False
    return b.domain is None or a.domain == b.domain


@dataclass
class TypeAssignment:
    """Result of τ: a type with confidence κθ."""

    type: SemType
    confidence: float = 1.0
    source: str = "schema"

    def certain(self, kappa_min: float) -> bool:
        return self.confidence >= kappa_min


# ---------------------------------------------------------------------------
# τ: structural + lexical typing of MCP schemas (used when no LLM typing exists)
# ---------------------------------------------------------------------------
_ARG_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|_)(url|uri|link|href)s?$"), "url"),
    (re.compile(r"(^|_)(path|file|filename|filepath|dir|directory|folder)s?$"), "path"),
    (re.compile(r"(^|_)(query|q|keyword|keywords|search|term|prompt|question)$"), "query"),
    (re.compile(r"(^|_)(sql)$"), "query:sql"),
    (re.compile(r"(^|_)(symbol|ticker|stock)s?$"), "identifier:stock"),
    (re.compile(r"(^|_)(repo|repository|owner)$"), "identifier:repo"),
    (re.compile(r"(^|_)(package|pkg|module|library)(_?name)?s?$"), "identifier:package"),
    (re.compile(r"(^|_)(date|time|datetime|timestamp|start_date|end_date|since|until)$"), "datetime"),
    (re.compile(r"(lat|lng|lon|latitude|longitude|location|address|city|origin|destination|place|region)"), "location"),
    (re.compile(r"(^|_)(id|uuid|key|name|slug|code)$"), "identifier"),
    (re.compile(r"(token|password|secret|api_key|apikey|credential)"), "credential"),
    (re.compile(r"(^|_)(content|text|body|message|markdown|description|paragraph|html)$"), "text"),
    (re.compile(r"(^|_)(data|rows|records|items|values|table)$"), "table"),
    (re.compile(r"(^|_)(code|script|command|cmd|expression)$"), "code"),
    (re.compile(r"(count|limit|num|number|amount|page|size|width|height|max|min|offset|top)"), "number"),
]

_OUT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(screenshot|image|picture|photo|icon|draw|paint|render)"), "media:image"),
    (re.compile(r"\b(chart|plot|graph|diagram|mindmap|word.?cloud)"), "media:chart"),
    (re.compile(r"\b(pdf|docx|word document|presentation|pptx|slide|spreadsheet|excel)"), "document"),
    (re.compile(r"\b(price|quote|stock)"), "record:stock"),
    (re.compile(r"\b(weather|forecast)"), "record:weather"),
    (re.compile(r"\b(route|direction|navigation)"), "record:route"),
    (re.compile(r"\b(search|results?)\b"), "record:search_result[]"),
    (re.compile(r"\b(list|all|issues|versions|history)\b"), "record[]"),
    (re.compile(r"\b(read|content|fetch|get text|transcript|summary)"), "text"),
]


def tau_arg(name: str, schema: dict | None, description: str = "") -> TypeAssignment:
    """τ for one argument: structural JSON type + lexical rules on the name."""
    n = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    jt = (schema or {}).get("type")
    for pat, t in _ARG_RULES:
        if pat.search(n):
            ty = parse_type(t)
            if jt == "array" and not ty.collection:
                ty = SemType(ty.kind, ty.domain, True)
            return TypeAssignment(ty, 0.8, "lex-arg")
    if jt in ("integer", "number"):
        return TypeAssignment(SemType("number"), 0.9, "schema")
    if jt == "boolean":
        return TypeAssignment(SemType("boolean"), 0.95, "schema")
    if jt == "array":
        return TypeAssignment(SemType("text", None, True), 0.4, "schema")
    if jt == "object":
        return TypeAssignment(SemType("record"), 0.4, "schema")
    return TypeAssignment(SemType("text"), 0.4, "schema")


_OUT_DOMAIN_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(npm|package|packages|module|dependency|dependencies)\b"), "package"),
    (re.compile(r"\b(audio|sound|music|mfcc|chroma|spectrogram|waveform|beat tracking)\b"), "audio"),
    (re.compile(r"\b(stock|stocks|equity|equities|ticker|finance|financial)\b"), "stock"),
    (re.compile(r"\b(news|headline|headlines|article|articles)\b"), "news"),
    (re.compile(r"\b(repository|repositories|repo|github)\b"), "repo"),
    (re.compile(r"\b(review|reviews|rating|ratings)\b"), "review"),
    (re.compile(r"\b(weather|forecast|meteorological)\b"), "weather"),
    (re.compile(r"\b(image|images|photo|photos|picture|pictures)\b"), "image"),
    (re.compile(r"\b(chart|charts|plot|plots|graph|graphs)\b"), "chart"),
    (re.compile(r"\b(issue|issues|ticket|tickets|bug|bugs)\b"), "issue"),
]


def _array_item_evidence(output_schema: dict | None) -> str:
    """Return shallow item-schema field evidence without interpreting arbitrary values."""
    if not isinstance(output_schema, dict) or output_schema.get("type") != "array":
        return ""
    items = output_schema.get("items")
    if not isinstance(items, dict):
        return ""
    props = items.get("properties")
    if isinstance(props, dict):
        return " " + " ".join(str(key) for key in props)
    return ""


def tau_out(name: str, description: str, output_schema: dict | None = None) -> TypeAssignment:
    """Type outputs from array structure plus conservative semantic domain cues.

    Array shape alone supports only generic record[]. A domain-specific array type
    requires a lexical cue in the tool name, description, or item field names.
    """
    text = (re.sub(r"[_\-]", " ", name) + " " + (description or "")[:500]
            + _array_item_evidence(output_schema)).lower()
    is_array = bool(output_schema and output_schema.get("type") == "array")
    if is_array:
        for pat, domain in _OUT_DOMAIN_RULES:
            if pat.search(text):
                return TypeAssignment(SemType("record", domain, True), 0.72, "schema+lex-domain")
        return TypeAssignment(SemType("record", None, True), 0.45, "schema-generic")
    for pat, t in _OUT_RULES:
        if pat.search(text):
            return TypeAssignment(parse_type(t), 0.55, "lex-out")
    return TypeAssignment(SemType("text"), 0.35, "default")

@dataclass
class TypeVocabulary:
    """Θ restricted to what a registry actually uses; offered to the analyst LLM."""

    types: set[str] = field(default_factory=set)

    def add(self, t: str | SemType) -> None:
        self.types.add(str(parse_type(t)))

    def as_list(self) -> list[str]:
        return sorted(self.types)
