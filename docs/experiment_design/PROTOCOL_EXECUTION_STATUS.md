# PaMCP E1–E22 — protocol execution gate

**Controlling documents:** the user-supplied \`Experimental_Protocol_PaMCP.docx\`, \`PaMCP_Experimental_Spec_v1.0\`, \`SPECIFICATION.md\`, \`experiment_matrix.csv\`, and \`pamcp_experimental_spec_v1.0.json\`. These take precedence over exploratory scripts and older result folders.

**Current decision:** E1's descriptive three-view registry census has been executed and its raw artifacts captured. The E1 run manifest is intentionally \`failed\` because the protocol's reference non-read-only share is not available from an admissible independent reference label set. E1 is therefore **not complete**, and E2/E3/E12 dependent execution is not released.

## E1 — executed descriptive census; reference metric blocked

Run: \`E1-20261104T223832Z-protocol-v1\`

- Branch: \`research/pamcp-experimental-v1\`
- Run commit: \`d28c34970144179023fbec9ef1da0c0b699414f2\`
- GitHub Actions run: [PaMCP E1 Protocol Run](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41926960347)
- Artifact: [PaMCP-E1-protocol-run](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/41926588281/artifacts/13369408582)
- Manifest validates against \`run_manifest.schema.json\`.
- All 25 checksummed run artifacts verified against \`ARTIFACTS_SHA256.json\`.
- Frozen raw source snapshots and the pre-run committed merged registry are included.
- The pinned raw rebuild exactly matches the committed 569-tool merged registry: 569/569 definitions, zero missing IDs, zero extra IDs, zero production canonical-hash mismatches.

### Registry measurements

| Registry view | Tools | Servers | Categories in view | Annotated tools | Annotated share | Declared \`readOnlyHint=true\` |
|---|---:|---:|---:|---:|---:|---:|
| LiveMCPTool | 525 | 69 | 8 | 44 | 8.38% | 44 / 8.38% |
| MCPToolBench++ | 87 | 10 | 6 | 0 | 0.00% | 0 / 0.00% |
| Merged | 569 | 76 | 12 | 44 | 7.73% | 44 / 7.73% |

The union of category labels across the two source registries is **14**, as specified. The merged registry has 12 observed labels because source category spelling is preserved (e.g. \`Finance\` and \`finance\`) and 43 overlapping definitions are de-duplicated. No case-folding or category consolidation was introduced.

| Description length (characters) | LiveMCPTool | MCPToolBench++ | Merged |
|---|---:|---:|---:|
| Mean | 221.49 | 145.25 | 218.57 |
| Median | 61 | 51 | 61 |
| P90 | 597.00 | 323.40 | 601.40 |
| Min–max | 0–3866 | 17–1235 | 0–3866 |

Tools per server: LiveMCPTool mean 7.61 (median 4); MCPToolBench++ mean 8.70 (median 7); merged mean 7.49 (median 4.5).

### Reference non-read-only metric — blocked

The E1 protocol names a **reference non-read-only share**. The repository contains LLM-produced silver effect/type labels, but those are not treated as independent reference labels. LiveMCPBench's task/tool-chain annotations are also not tool-effect ground truth. No admissible, complete reference label set was supplied.

Consequently:
- Reference label coverage is 0/525, 0/87 and 0/569 for the three views.
- Reference non-read-only counts/shares are \`null\` (not zero).
- No non-read-only labels were inferred from tool names, descriptions, annotations or lexical effects.
- The two blank effect-annotation sheets and restricted mapping are included in the E1 bundle as an operational way to collect independent reference labels. **This two-annotator workflow is an added data-quality safeguard; the v1.0 E1 entry itself does not prescribe its annotation protocol.** The label provenance and any adjudication rules must be recorded before scoring the reference metric.

### Data quality and status

| Gate | Result |
|---|---|
| Source revisions pinned | Pass |
| Source tool/server counts | Pass: 525/69, 87/10 |
| Merged count | Pass: 569/76 |
| Category union | Pass: 14 |
| Committed merged registry vs. pinned rebuild | Pass: exact match |
| Production definition hashes | Pass: 0/569 mismatches |
| Manifest schema | Pass |
| Raw source and merged snapshots in ZIP | Pass |
| Reference non-read-only labels | **Blocked: missing independent reference labels** |

The runner's manifest status is \`failed\` by design until the reference metric is supported. A successful CI job means the descriptive execution and artifact validation succeeded; it does not mean the experiment is scientifically complete.

## Required sequence and readiness

| Series | Protocol dependency | Current evidence | Decision |
|---|---|---|---|
| E1 | None | Three-view descriptive census complete; reference non-read-only share blocked | Await independent reference labels; then rerun E1 and accept |
| E2 | E1; human-annotated tool subset | Paired blank semantic-typing annotation preparation exists; no completed annotations | Prepare/freeze sample and scoring contract; do not score yet |
| E3 | E1; runnable credential-free reference servers | Registry definitions exist; no confirmed runnable server inventory or observed traces | Inventory servers and build isolated probe harness |
| E12 | Purpose-built calibration sets | Existing checked-in calibration data does not meet the protocol's 10 classes, log-spaced 10–30,000 sizes, Latin/Arabic/CJK scripts and three models | Build and freeze new corpus |

The protocol says E2, E3 and E12 are prerequisites because semantic contracts, observed effects and model profiles feed later series. E2/E3 follow E1; E12 additionally requires the specified new calibration-set freeze.

## Next actionable work

1. Collect and freeze the independent E1 reference non-read-only labels for the 569 unique source-union definitions. Join by \`tool_id\` and full SHA-256 definition hash, document provenance/adjudication, and rerun E1.
2. Freeze E2's human-annotated tool subset, evidence-condition procedure, matching rule, uncertainty/abstention handling and scoring protocol before two annotators see the targets. Do not use silver labels as gold.
3. Inventory credential-free reference servers for E3; record exact versions and tool-definition hashes, sandbox boundaries, probe generators, probe budgets (10/30/100), and observed traces.
4. Rebuild and freeze E12's calibration data to cover all ten task classes, log-spaced sizes 10–30,000, the three script families and three models.
5. Only after E1/E2/E3/E12 prerequisite artifacts are accepted, proceed through the downstream experiment dependency graph.

## Explicit prohibitions

- No replay of the old E0–E7 exploratory pipeline as definitive evidence.
- No use of Claude/LLM silver labels as independent ground truth.
- No claim that metadata or lexical inference is observed effect evidence.
- No claim of actual MCP execution when only a local adapter preview or registry record was used.
- No downstream experiment status is changed to completed without a spec-valid manifest and required raw artifacts.

**CI regression result:** the E1 protocol workflow completed successfully; both E1 protocol runner tests passed. The full regression workflow also installs the `experiment` extra so the manifest-validation dependency is present during collection.
