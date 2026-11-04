# PaMCP E1–E22 — protocol execution gate

**Controlling documents:** the supplied \`Experimental_Protocol_PaMCP.docx\` and \`PaMCP_Experimental_Spec_v1.0\`. These take precedence over exploratory scripts and older result folders.

**Current decision:** E1 is a preliminary data pass, not an accepted protocol-compliant run. Do not start dependent experiments or report definitive results from it.

## E1 audit

| Protocol requirement | Existing E1 package | Gate |
|---|---|---|
| Separate LiveMCPTool view | Merged-source contribution (525 rows) only | Incomplete |
| Separate MCPToolBench++ view | Merged-source contribution (44 rows), not original 87-tool corpus | Incomplete |
| Merged registry view | 569 tools reported | Partial |
| Annotated share / read-only declared share | Present for merged snapshot | Partial |
| Reference non-read-only share | Not reported; no independent reference labels located | Blocked |
| Tools per server / description length | Merged snapshot only | Partial |
| Category summary | Computed from merged, de-duplicated rows; does not replace the three requested registry views | Incomplete |
| Frozen raw input in run archive | No registry snapshot in ZIP | Fail |
| Run manifest | Fails supplied \`run_manifest.schema.json\` (missing \`spec_version\` and other required fields) | Fail |
| Hash validation | Eight provisional JavaScript candidates; exact Python canonical check remains pending | Pending |

Important: the 525/44 figures are contributions retained in the **de-duplicated merged registry**. They are not the original source corpus sizes. The repository data loader documents 525 LiveMCPTool tools, 87 MCPToolBench++ tools, and 569 merged tools. The overlap is lost if 525/44 is misreported as the source registry sizes.

The repository contains LLM-produced silver effect/type labels. The protocol requires independent reference labels for E1/E2; the silver labels must not be substituted for human gold.

## Required sequence and readiness

| Series | Protocol dependency | Current evidence | Decision |
|---|---|---|---|
| E1 | None | Preliminary merged-only pass; missing source-specific views, reference non-read-only metric, frozen input, spec-valid manifest and hash revalidation | Correct and rerun E1 |
| E2 | E1; two human annotators | No independent two-annotator semantic-type reference set found in the repository | Prepare intake; do not score yet |
| E3 | E1; runnable credential-free reference servers | Registry definitions exist, but no confirmed runnable reference-server inventory or frozen observed-effect traces were found | Inventory servers and build probe sandbox |
| E12 | Calibration-set freeze | Existing checked-in bundle covers four task classes, sizes 10/40/160/640 and two model answer files; it does not satisfy 10 classes, log-spaced 10–30,000 sizes, Latin/Arabic/CJK scripts and three models | Rebuild/freeze E12 dataset |

The supplied specification says E2, E3 and E12 are prerequisites because semantic contracts, observed effects and model profiles feed later series. E2/E3 depend on E1; E12 additionally requires a new calibration-set freeze.

## Next actionable work

1. Rerun E1 on all three required registry views, with original source counts, the specified category reporting, tools/server and description-length distributions, independent reference non-read-only labels, raw input snapshots, Python canonical hash verification, and a manifest validated against the supplied schema.
2. Freeze E2 sample size, seed/design, scoring rules and dataset hash; produce two separate blinded annotation sheets. \`experiments/e2/prepare_annotation_tasks.py\` creates blank sheets only; it does not generate labels or results.
3. Inventory runnable, credential-free MCP servers for E3; record exact versions, tool definitions, sandbox boundaries, probe generators and observed traces.
4. Freeze the redesigned E12 calibration corpus across all prescribed classes, size buckets, scripts and three models before collecting model responses.
5. Only after prerequisite run artifacts are validated, proceed to E4–E8 and then the downstream dependency graph.

## Explicit prohibitions

- No replay of the old E0–E7 exploratory pipeline as definitive evidence.
- No use of Claude/LLM silver labels as independent human ground truth.
- No claim that metadata or lexical inference is observed effect evidence.
- No claim of actual MCP execution when only a local adapter preview or registry record was used.
- No downstream experiment status is changed to completed without a spec-valid manifest and required raw artifacts.
