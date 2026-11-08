# PaMCP final evaluation — findings

Branch `research/pamcp-final-evaluation`. Methods: `docs/FINAL_EVALUATION_METHODS.md`; plan, evidence classes and
the preregistered confirmatory family: `docs/FINAL_EVALUATION_PLAN.md`; every number below is in
`docs/FINAL_EVALUATION_TABLES.md` (generated from `results/final/*.json`; raw per-item records in
`results/final/raw/`). Each result file carries a run id, the code commit and content hash, input, label and
LLM-record hashes, and its configuration.

<!-- SUMMARY -->

## Evidence ledger

| Series | Status | Evidence class |
|---|---|---|
| E1 Registry characterisation | run (3 views) | MEASURED; LABELLED for the not-read-only share |
| E2 Semantic typing | proxy run; human study BLOCKED (sheet prepared) | LABELLED (agreement, not accuracy) |
| E3 Declared vs observed effects | declared/lexical vs labels B; observed BLOCKED | LABELLED |
| E4–E7 Exposure, forgery, verifier, trust | run | SIMULATED evidence, LABELLED scoring |
| E8 Single-tool retrieval | run | MEASURED (benchmark gold) |
| E9 Set retrieval | run | MEASURED (benchmark gold) |
| E10 Set validity | run | LABELLED (independent evaluator) |
| E11 Capability gap | partial (task success BLOCKED) | MEASURED (engine) |
| E12 Profile calibration | partial (64-item set, 3 models) | MEASURED |
| E13 End-to-end execution | BLOCKED | — |
| E14 Prompt injection | offline only | LABELLED |
| E15 Scalability | run | SYNTHETIC, MEASURED latency |
| E16 Evolution | run | MEASURED |
| E17 Refinement | partial (LLM-free repairs) | MEASURED |
| E18 Factorial ablation | run (task success BLOCKED) | MEASURED / LABELLED |
| E19 LLM role configurations | not run | — |
| E20 Sensitivity | run | MEASURED / LABELLED |
| E21 Experience reuse (AutoTool) | BLOCKED | — |
| E22 Statistics | run | — |

## Reference labels and reproducibility

The blind second labelling (labels B, Claude Opus) agrees with labels A (Claude Sonnet) on 558 of 569 tools
for state modification (κ = 0.944) and on private output with κ = 0.893. Every tool that is not read-only under
B is also not read-only under A (A marks 131 tools, B 120), so verifier evidence simulated from A excludes every
tool B considers unsafe; the independence of B tests over-exclusion, not under-exclusion. Both labellings come
from one model family. Re-running E4, E11 and E12 from the committed code reproduced every reported metric
exactly (1,920 E4 metrics compared).

## E1–E3 Registry, typing and declared effects

* The three views reproduce Table 1 (76 servers, 569 tools, 44 annotated tools on three servers, all declaring
  `readOnlyHint=true`). The original MCPToolBench++ tool set has 87 tools on 10 servers; 43 of them and 3 of the
  servers coincide with LiveMCPTool. Under labels B, 120 tools (21.1%, 95% CI 17.9–24.6%) are not read-only;
  one annotated tool (`opgg-mcp::lol-summoner-renewal`) declares read-only but is not.
* Declarations cover 44 tools, one of them wrong; the other 525 tools, including 119 that are not read-only,
  declare nothing. Lexical cues flag 82.5% of the unsafe tools at precision 0.54.
* Typing: the LLM typing τ used by the engine agrees with labels B on 78.9% of output kinds (κ 0.718, macro-F1
  0.704); the engine's structural typer alone agrees on 22.8% (κ 0.070). Agreement on the full type (kind and
  domain) is 35.7% for τ. This is agreement between two LLM labellings, not accuracy; the human study needs the
  prepared sheet to be filled.

## E4 Exposure under policy encodings

394 requests (300 MCPToolBench++ + 94 LiveMCPBench); 273 have only read-only gold tools under B and form the
Exp@5/Util@5 denominator.

* With no filter (and with MCP's default of displaying annotations without enforcing them) 42.5% of the
  requests get an unsafe tool in PaMCP's top-5 (all 120 unsafe tools are eligible). Closed-world annotations
  admit 44 tools and one unsafe tool, but that tool still reaches 31.5% of the top-5 lists because the pool is
  so small, and utility collapses to 0.4%. Lexical filtering admits 21 of the 120 unsafe tools (Exp@5 9.9%,
  Util@5 41.0%); on this registry the positive and closed-world lexical encodings coincide.
* Verified evidence admits none of the unsafe tools (Exp@5 0% for every retriever) and keeps 77.0% of the
  registry eligible; Util@5 is 46.2% for PaMCP's retrieval stage against 49.8% unfiltered, and 72.2% against
  76.6% for MCP-Zero. As the verifier probes fewer tools, exposure stays at zero and utility falls with the
  eligible share (Util@5 34.7%, 26.8% and 16.3% at coverage 0.75, 0.5 and 0.25).
* The zero exposure follows from the simulation (see Reference labels); the measured content is the utility
  cost and the contrast with the metadata encodings.

## E5 Forged and laundered metadata

Attacker servers (fraction δ, 5 seeds) declare all their tools read-only and/or launder their descriptions; the
verifier has a 5% false-accept rate. Exp@5 / Util@5, PaMCP retrieval stage:

* Forged annotations are what break the closed-world annotation encoding: its exposure rises from 31.5% (δ = 0)
  to 56.8% at δ = 0.1 and 62.6% at δ = 0.3, while utility stays at or below 19.2%.
* Laundering alone barely moves any encoding, because the laundered descriptions keep the tool names, from which
  the lexical labeller takes most of its cues (this favours the lexical encodings): lexical Exp@5 stays between
  8.7% and 9.9%.
* Verified evidence is independent of δ; with a 5% false-accept rate its exposure is 5.4–5.6% (0.0% with the
  single seed at δ = 0) at Util@5 46.1–46.9%.

<!-- E6-E7 -->

## E8 Single-tool retrieval

* On the MCPToolBench++ tool set (B1, 81 tools: the tools only in MCPToolBench++ or used as gold) PaMCP's
  goal-contract retrieval ranks the gold tool first for 66.0% of the 300 sampled requests, second to MCP-Zero's
  model-written requests (68.0%) and ahead of raw-text RRF (54.3%).
* On the merged registry (569 tools) it falls to 23.0%, below every other method (raw-text RRF 38.7%, BM25
  39.7%, MCP-Zero 50.0%, COLT 35.0%, ToolScope 36.0%, CMTF 33.3%); the distractor curve shows the drop growing
  with each added block of LiveMCPTool tools. Confirmatory test F7 (goal contract vs raw-text RRF) therefore
  goes against PaMCP (Δ = −0.157).
* Diagnosis (`E8_diagnostic`): the analyst's goal text alone ranks better than the raw request (Hit@1 40.0% vs
  38.7%); adding the structural component of Eq. (5) drops it to 23.0%, because only 50.3% of the gold tools
  are type-compatible with the analyst's goal output type. With coarse or mismatched typing the structural
  ranking promotes type-compatible wrong tools.
* With 66 target tools for 300 requests, CIs that resample target tools are about three times wider than
  request-level CIs (E22).

<!-- E9-E10 -->

## E11 Capability gap (review scenario)

On the review scenario of Fig. 1 the gap grows with input size: with tolerant aggregation the toolkit has 2
tools (60% of the goals native) at n = 30 and 300 and 6 tools at n = 3,000 (τ ≥ 0.75), and the engine abstains
at n = 30,000; exact aggregation adds two tools at n = 30 and 300. With τ = 0.6 the engine already abstains at
n = 3,000. The three measured profiles give the same
toolkits, because Sonnet and Opus answered all 64 calibration items correctly and the scenario's native classes
use the same declared priors beyond the measured sizes. Without gap analysis the engine abstains in every
setting (no registry tool serves the native goals). With the 569 public tools added to this scenario's registry,
the engine abstains with a χ1 counterexample because the K = 5 shortlist of the report goal fills with public
document tools.

## E12 Model profile calibration

Sonnet and Opus answered all 64 items correctly (including exact sums of 640 numbers); Haiku 51 of 64 (exact
sums 1/4 at n = 160 and 0/4 at n = 640, counts 0/4 at n = 640). All three models underestimated themselves when
asked beforehand: mean signed error −0.23 (Sonnet), −0.22 (Haiku), −0.30 (Opus); MAE 0.23, 0.24 and 0.30.
Self-assessment alone would therefore have sent work to tools that the model does correctly. The engine's
profile refuted 12 of the 128 native claims of the analyst (9.4%).

<!-- E14-E22 -->
