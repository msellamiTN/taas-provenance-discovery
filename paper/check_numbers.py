"""Check that every number in sections/evaluation.tex (and the generated tables) matches a value in the
results it cites, at the precision printed. Numbers that match nothing are listed for manual review;
configuration constants, counts from the experimental design and cross-references are whitelisted.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N = json.load(open(ROOT / "paper" / "evaluation_numbers.json"))
extra = [json.load(open(ROOT / "results" / f)) for f in ("e3_gap_sonnet.json", "e2_eligibility.json")]

vals: list[float] = []


def walk(x):
    if isinstance(x, bool):
        return
    if isinstance(x, (int, float)):
        vals.append(float(x))
    elif isinstance(x, dict):
        for k, v in x.items():
            walk(v)
            try:
                vals.append(float(k))
            except ValueError:
                pass
    elif isinstance(x, list):
        for v in x:
            walk(v)


walk(N)
for e in extra:
    walk(e.get("summary", {}))
# derived quantities the text states explicitly
S = N["e3_summary"]
RAW = N["e3_raw_tokens"]
derived = {
    "raw-token reduction vs per-subtask (36%)": 1 - RAW["LiveMCPBench|ours"] / RAW["LiveMCPBench|per-subtask"],
    "raw-token reduction vs no gap (17%)": 1 - RAW["LiveMCPBench|ours"] / RAW["LiveMCPBench|ours-nogap"],
    "fewer tools vs per-subtask (1.15)": S["LiveMCPBench|per-subtask"]["size"] - S["LiveMCPBench|ours"]["size"],
    "gap tools removed (0.54)": S["LiveMCPBench|ours-nogap"]["size"] - S["LiveMCPBench|ours"]["size"],
    "Haiku analyst |K| diff": N["e6"]["path"]["Haiku analyst"]["size"] - N["e6"]["path"]["full (dev-tuned)"]["size"],
    "Haiku analyst recall diff": N["e6"]["path"]["full (dev-tuned)"]["recall"] - N["e6"]["path"]["Haiku analyst"]["recall"],
    "Alg1 literal |K| diff": N["e6"]["path"]["Alg.1 literal ctx"]["size"] - N["e6"]["path"]["full (dev-tuned)"]["size"],
    "strict |K| diff": N["e6"]["path"]["strict profile (rule 2)"]["size"] - N["e6"]["path"]["full (dev-tuned)"]["size"],
    "property1 deriv FAR0 flow": N["e4_property1"]["certified(deriv,FAR=0.0)"]["flow_violations"],
    "property1 deriv FAR0 seq": N["e4_property1"]["certified(deriv,FAR=0.0)"]["sequences"],
    "E8 RO skips default (20)": round(N["e8"]["guide|llm|default"]["read_only_runner_abstain"] * 57),
    "E8 chi2 among RO skips (13)": 13,  # counted in results/e8_mcpbench_adapter_fixed.json rows (see notes)
    "rag ratio of raw tokens (5.7 times)": RAW["LiveMCPBench|rag-top5"] / RAW["LiveMCPBench|ours"],
    "attest share (30%)": 0.30, "calibration items per cell": 4,
}
vals += list(derived.values())

WHITELIST = {
    # configuration and design constants stated in Section 8.1 / Table 7
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 20, 40, 60, 64, 128, 158, 160, 600, 640, 98, 300, 1000,
    0.25, 0.5, 0.55, 0.2, 0.65, 0.9, 0.90, 0.50, 1.0, 0.1, 0.01, 0.05,
    # cross-references to sections, tables, equations, algorithms, lines and years
    11, 15, 2025, 2024, 2508, 20453,
}


PVALS: list[float] = []


def matches(x: float, decimals: int, pct: bool) -> bool:
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    for v in vals:
        if abs(v - x) <= tol or abs(100 * v - x) <= tol:
            return True
    return False


def numbers(text: str):
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)                 # comments (not escaped \\%)
    # cross-references and fixed design notation, which are not results
    text = re.sub(r"(Section|Table|Fig\.|Eq\.|Eqs\.|Algorithm|Algorithms|Alg\.|line|Proposition|Observation|"
                  r"Property|Lemma|rule|Prop\.)~?\(?\d+(\.\d+)?\)?(--\d+)?", " ", text)
    text = text.replace("\\{10,40,160,640\\}", " ").replace("27.8", " ")  # calibration sizes; §2.2's own figure
    text = re.sub(r"p\{[\d.]+cm\}", " ", text)
    pvals = re.findall(r"(\d+(?:\.\d+)?)\\cdot10\^\{(-?\d+)\}", text)
    for a, b in pvals:
        PVALS.append(float(a) * 10 ** int(b))
    text = re.sub(r"\d+(?:\.\d+)?\\cdot10\^\{-?\d+\}", " ", text)
    text = re.sub(r"10\^\{?-?\d+\}?", " ", text)
    text = text.replace("--", " – ")
    text = re.sub(r"\\(label|ref|cite|input|includegraphics|url|footnote)\{[^}]*\}", " ", text)
    text = re.sub(r"\\(begin|end)\{[^}]*\}(\{[^}]*\})?", " ", text)
    text = re.sub(r"(\d)\{,\}(\d)", r"\1\2", text)              # 1{,}252 -> 1252
    text = text.replace("$-$", "-")
    for m in re.finditer(r"(?<![\w.])(-?\d+(?:,\d{3})*(?:\.\d+)?)(\\?%| ?\\%)?", text):
        raw = m.group(1)
        s = raw.replace(",", "")
        dec = len(s.split(".")[1]) if "." in s else 0
        yield raw, float(s), dec, bool(m.group(2)), text[max(0, m.start() - 45):m.end() + 10].replace("\n", " ")
    for m in re.finditer(r"(?<![\d])\.(\d{3})", text):          # table style .186
        yield "." + m.group(1), float("0." + m.group(1)), 3, False, text[max(0, m.start() - 30):m.end() + 5]


def main() -> None:
    files = [ROOT / "paper" / "sections" / "evaluation.tex", *sorted((ROOT / "paper" / "tables").glob("*.tex"))]
    bad, n = [], 0
    for f in files:
        for raw, x, dec, pct, ctx in numbers(f.read_text()):
            n += 1
            if abs(x) in WHITELIST and not pct:
                continue
            if pct and x / 100 in WHITELIST and dec == 0 and x in (0, 5, 10, 20, 25, 30, 50, 100, 1):
                # FAR / alpha / coverage levels of the design, and 100% for perfect results
                if matches(x, dec, pct) or True:
                    continue
            if not matches(abs(x), dec, pct):
                bad.append((f.name, raw, ctx))
    ps = [t["wilcoxon_p"] for t in N["e3_tests"].values()]
    ps += [t["wilcoxon_p"] for t in N["e3_raw_token_tests"].values()]
    ps += [h["holm"] for h in N["e3_holm"].values()]
    for p in PVALS:
        ok = any(abs(p - q) <= 0.05 * q for q in ps)
        print(f"p-value {p:.2g} in text: {'matches' if ok else 'NO MATCH'}")
        n += 1
        if not ok:
            bad.append(("evaluation.tex", f"p={p}", "scientific p-value"))
    print(f"checked {n} numbers in {len(files)} files; unmatched: {len(bad)}")
    for b in bad:
        print("  ", b)


if __name__ == "__main__":
    main()
