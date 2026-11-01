# GitHub research: repositories closest to TaaS

Scope: public code near "Tool-as-a-Service: Provenance-Aware Tool Discovery for LLM Agents in MCP Ecosystems" (Sellami & Mezni). Snapshot taken 2026-11-01. Stars come from the GitHub search API on that date. Repositories were shallow-cloned and their source read; **no cloned code was executed**. Clones live in the session scratchpad (`.../scratchpad/ghr/`), outside this repository. Items marked *(unverified)* could not be confirmed in this environment (Hugging Face is blocked; the `gh` CLI is unauthenticated).

## (a) Discovery table

| Repo | Paper | Public code | Stars | License |
|---|---|---|---|---|
| RAG-MCP | arXiv 2505.03275 | **No** official code found (arXiv page has no link; GitHub search returns only unrelated repos) | n/a | n/a |
| [xfey/MCP-Zero](https://github.com/xfey/MCP-Zero) | 2506.01056 | Yes | 517 | MIT |
| [EliasLumer/ScaleMCP](https://github.com/EliasLumer/ScaleMCP) | 2505.06416 | Placeholder only: README + LICENSE, no source | 2 | Apache-2.0 |
| [EliasLumer/Graph-RAG-Tool-Fusion-ToolLinkOS](https://github.com/EliasLumer/Graph-RAG-Tool-Fusion-ToolLinkOS) | 2502.07223 | Data only (ToolLinkOS JSON), no retrieval code | 23 | MIT |
| Agent-as-a-Graph | 2511.18194 | **No** code found | n/a | n/a |
| [mangopy/tool-retrieval-benchmark](https://github.com/mangopy/tool-retrieval-benchmark) (ToolRet) | 2503.01763 | Yes (eval + training; data on HF, *unverified*) | 220 | Apache-2.0 |
| [quchangle1/COLT](https://github.com/quchangle1/COLT) | 2405.16089 | Yes | 27 | **None declared** |
| [zhiqiangwang4/MCPTox-Benchmark](https://github.com/zhiqiangwang4/MCPTox-Benchmark) | 2508.14925 | Data + poisoned server stubs (owner matches first author, *unverified*) | 15 | **None declared** |
| MCPSHIELD | 2604.05969 | **No** code found (name collisions are unrelated scanners) | n/a | n/a |
| [vineethsai/python-sdk-etdi](https://github.com/vineethsai/python-sdk-etdi) (ETDI) | 2506.01333 | Yes, fork of the MCP Python SDK with `src/mcp/etdi` (authorship link *unverified*); docs repo `vineethsai/MCP-ETDI-docs` (8 stars, no license) | 1 | MIT |
| [sunblaze-ucb/progent](https://github.com/sunblaze-ucb/progent) | 2504.11703 | Yes | 58 | MIT |
| [google-research/camel-prompt-injection](https://github.com/google-research/camel-prompt-injection) | 2503.18813 | Yes (research artifact, unmaintained) | 414 | Apache-2.0 |
| [microsoft/fides](https://github.com/microsoft/fides) | 2505.23643 | Tutorial notebook only | 125 | MIT |
| [microsoft/fides-gateway](https://github.com/microsoft/fides-gateway) | follow-on, not the paper | Yes, MCP proxy with IFC labels | 2 | MIT |
| [ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo) | 2406.13352 | Yes | 974 | MIT |
| [icip-cas/LiveMCPBench](https://github.com/icip-cas/LiveMCPBench) | 2508.01780 | Yes | 105 | Apache-2.0 |
| [mcp-tool-bench/MCPToolBenchPP](https://github.com/mcp-tool-bench/MCPToolBenchPP) | 2508.07575 | Yes | 46 | MIT |
| [modelcontextprotocol/registry](https://github.com/modelcontextprotocol/registry) | n/a | Yes (Go) | 7,424 | Apache-2.0, mid-transition from MIT (mixed per contribution) |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | n/a | Yes (TS/Python) | 91,735 | same mixed MIT/Apache-2.0 |
| *extra:* [pipelab-org/pipelock](https://github.com/pipelab-org/pipelock) | n/a | Yes (Go MCP firewall) | 976 | Apache-2.0 |
| *extra:* [cicorias/hyset-poc](https://github.com/cicorias/hyset-poc) | HySet, 2607.25718 (Hong et al.) | Third-party clean-room PoC, not the authors' code; paper claims not checked | 0 | MIT |

## (b) Deep-read repositories

Paths are relative to each repo root.

**MCP-Zero** (`fd666c4`)
- `MCP-zero/matcher.py::ToolMatcher` runs two-stage routing: `match_servers` scores each server by `max(cos(desc_emb), cos(summary_emb))` and keeps `top_servers`; `match_tools` ranks tools inside those servers by `server*tool*max(server,tool)`.
- The LLM emits `<tool_assistant>server:/tool:` blocks; `extract_tool_assistant` parses them with a regex. This is the active-request loop (prompts in `MCP-zero/prompt_guide/*.prompt`).
- `MCP-tools/build_data/get_server_summary.py` builds per-server LLM summaries from READMEs (the index-construction step). `MCP-zero/sampler.py` runs needle-in-a-haystack tool-count scaling.
- Dense-only, one embedding per tool; no effects, no provenance, no set-level view.

**ToolRet** (`c4181d9`) and **COLT** (`bbec292`)
- `toolret/eval.py::eval_retrieval` encodes `tool['documentation']`, searches a FAISS inner-product index, and `trec_eval` reports NDCG/MAP/Recall/Precision plus **`Comprehensiveness@k`** (all gold tools in top-k).
- ToolRet queries carry an `instruction` and `labels=[{id, doc, relevance}]`; task and category lists are in `toolret/config.py`.
- `COLT/models/COLT.py::COLT` builds three graphs: query-tool, query-scene and scene-tool bipartite (`get_tool_level_graph`, `get_scene_level_graph`, `get_scene_agg_graph`). A "scene" is a co-used tool bundle, i.e. a hyperedge as an incidence matrix. `cal_c_loss` adds contrastive learning.
- `COLT/train.py::calculate_completeness` is the "all relevant in top-k" metric. Data is BEIR-style (`corpus.jsonl`, `queries.jsonl`, `qrels/*.tsv`, `scene_tool.txt`).

**HySet PoC** (`0494ebd`, third party)
- `src/hyset/inference.py::SetRetriever` runs stage 1 (`shortlist`: top-K1 tools plus complementarity expansion) and stage 2 (`best_sets`: exhaustive argmax over all 1..M subsets of the shortlist, 21,699 at K=20, M=5). `greedy_rank` is the marginal-gain order.
- `src/hyset/model.py::HySet` scores a set as a pairwise interaction term (one matrix per set size) plus an attention-pooled query alignment term. `serve/mcp_server.py` exposes `select_tools`.
- Sets are scored for co-invocation likelihood only; there is no typing, no consumability check and no constraint model.

**Progent** (`b02783b`)
- `secagent/tool.py` holds `security_policy = {tool: [(priority, effect, arg_restrictions, fallback)]}`. `check_tool_call` and `_check_tool_call` enforce deterministically: 0 = allow, 1 = forbid, fallbacks are message, terminate or user-confirm. Restrictions are a JSON Schema, a regex or a callable.
- `generate_security_policy` has an LLM draft least-privilege args from the user query at priority 100; `generate_update_security_policy` narrows or widens it from tool results.
- `secagent/policy_analysis.py::security_policy_subset_check` uses Z3 to verify an updated policy stays within the original. `policy_type_check.py` type-checks policies against tool schemas.
- `secagent/progent_proxy.py` is a FastMCP proxy: `ListingFilterMiddleware.on_list_tools` filters the visible tool set, `ToolCallFilterMiddleware.on_call_tool` enforces. `update_always_allowed_tools` is a per-suite hard-coded allowlist (no evidence).

**FIDES** (`669c046`) and **fides-gateway** (`3f39af1`)
- `microsoft/fides/Tutorial.ipynb` defines `ConfidentialityLabel`, `IntegrityLabel`, `ProductLabel` and `InverseLattice`. `LabeledPlanningLoop` joins labels as tool results arrive; `policy_no_untrusted_declassification` raises `PolicyViolation`.
- `fides-gateway/lattice.py`: `SecurityLattice = ProductLattice[IntegrityLattice, InverseLattice[Users]]`. Join is the LUB (intersect readers), `"public"` is the bottom, and `IFCLabels` is the wire format in `_meta["com.github.ifc/labels"]`.
- `middleware.py::ToolAnnotationsMiddleware` / `_merge_annotations` injects `readOnlyHint` / `destructiveHint` / `openWorldHint` into `tools/list`; **upstream-provided annotations win** over configured ones.
- `policy_engine.py::eval_policy` evaluates Rego (regorus) with an `ifc.label(jsonpath)` extension. `PolicyMiddleware` attaches per-tool Rego, and `policies/*.rego` check the server version.

**CaMeL** (`f083b6b`)
- `src/camel/capabilities/capabilities.py::Capabilities(sources_set, readers_set)` is attached to every interpreter value; `interpreter/value.py::CaMeLValue.get_dependencies` carries the data-flow DAG.
- `capabilities/utils.py::get_all_readers` (intersection over the dependency closure), `get_all_sources` and `is_trusted` compute the effective label. `sources.py::SourceEnum` is `CaMeL | User | Assistant | TrustedToolSource`.
- `security_policy.py::SecurityPolicyEngine.check_policy` is called from `interpreter/interpreter.py` before each tool call. It allows `no_side_effect_tools`, denies state-changing calls depending on private values, then dispatches per tool by `fnmatch`; the default is deny. Per-suite policies live in `pipeline_elements/security_policies/{banking,slack,travel,workspace}.py`.

**ETDI** (`ff8403d`) and **pipelock** (`3ff6f5e`)
- `src/mcp/etdi/client/approval_manager.py::ApprovalManager._calculate_definition_hash` hashes sorted JSON of `{id, name, version, description, provider, permissions, schema}`. `check_for_changes` diffs version, provider, scopes and hash. `client/verifier.py::check_tool_before_invocation` returns `requires_reapproval`, but its `_detect_changes` does not compare the hash.
- ETDI's hash omits `annotations` and `outputSchema`, so an annotation flip would not change it.
- `pipelock/internal/mcp/tools/tools.go::ToolBaseline` keeps per-tool SHA-256 baselines, a structural digest and a session-bound known-tool set. `CheckAndUpdatePromote` and `EvaluateDefinition` report drift.
- `pipelock/internal/mcp/provenance/sign.go::ToolDigestRaw` hashes the **whole** canonical tool object (annotations, outputSchema, `_meta` minus its own attestation). `SignPipelock` produces Ed25519 attestations with a SLSA predicate embedded in `_meta`, and `VerifyToolsList` checks them. This is the closest thing to the paper's `att` evidence.

**MCP registry** (`01e5c93`) and **reference servers** (`194cc86`)
- `pkg/model/types.go::Package` carries `FileSHA256` (required for `mcpb`, which clients must verify), exact versions only, and `Repository.ID` (to detect repository resurrection).
- `internal/auth/types.go` lists publisher auth methods: `github-at`, `github-oidc`, `oidc`, `dns`, `http`. `internal/validators/registries/{npm,pypi,...}.go` plus `mcpname.go::containsMCPNameToken` prove package-to-name ownership via an `mcp-name:` token.
- `pkg/api/v0/types.go` stores `Status` (active/deprecated/deleted) and `_meta` with `io.modelcontextprotocol.registry/official` and `.../publisher-provided`.
- `servers/src/filesystem/server.ts` registers tools with `annotations` and `outputSchema`. `src/everything/server/context.ts::toolsChanged` calls `sendToolListChanged`; `tools/trigger-list-changed.ts` is a ready-made `list_changed` emitter for tests.

**Benchmark repos** (data formats are in section c)
- **LiveMCPBench**: `baseline/mcp_copilot/{router.py::Router.route, matcher.py::ToolMatcher}` is explicitly adapted from MCP-Zero; `server.py` exposes MCP tools `route` and `execute-tool`.
- **MCPToolBench++**: `src/mcp_tool_bench/agents/base_tool_call_agent/check_functions.py::check_multi_tool_call_dag` scores only the **last** call node (plus `similar_tools` aliases).
- **AgentDojo**: `agent_pipeline/planner.py::ToolSelector` and the `tool_filter` defense do LLM-based tool narrowing. `base_tasks.py` pairs `BaseUserTask.ground_truth -> list[FunctionCall]` with `utility()`, and `BaseInjectionTask.GOAL` with `security()`.

## (c) Technique map

| Paper concept | Closest comparable (repo: file::symbol) | Gap |
|---|---|---|
| Tool retrieval (lex + dense + structural, RRF) | MCP-Zero `matcher.py::match_tools`; ToolRet `eval.py::eval_retrieval`; Agent-as-a-Graph wRRF (paper only) | No public hybrid with RRF and a structural term, and none restricted to an eligible set |
| Server routing | MCP-Zero `match_servers`; LiveMCPBench `Router.route` | Routing ignores server provenance |
| Dependency graph / backward closure | ToolLinkOS `depends_on` (data only); AgentDojo nested `FunctionCall`; MCPToolBench++ DAG check | No typed consumability/producibility closure; ScaleMCP and Graph RAG-Tool Fusion traversal code unreleased |
| Set-level retrieval / completeness | ToolRet `Comprehensiveness@k`; COLT `calculate_completeness`; HySet `SetRetriever.best_sets` | Set scored for co-occurrence, not sufficiency against typed goals, cost or constraints |
| Annotation / effect handling | servers `filesystem/server.ts` hints; fides-gateway `_merge_annotations`; CaMeL `no_side_effect_tools` | Annotations are trusted or hard-coded; none is an untrusted, ordered evidence level |
| Information-flow control | CaMeL `get_all_readers`/`is_trusted`; FIDES notebook labels; fides-gateway `SecurityLattice`, `eval_policy` | All runtime and per value; no static pre-execution flow bound over a toolkit |
| Privilege policies | Progent `check_tool_call`, `security_policy_subset_check`; CaMeL `check_policy`; fides-gateway Rego | They gate calls; none gates which tools may be *retrieved* by evidence threshold |
| Definition pinning / hashing | pipelock `ToolBaseline`, `ToolDigestRaw`; ETDI `_calculate_definition_hash`; registry `FileSHA256` | Evidence is not keyed to `(tool, hash)` and restored on re-appearance; caches are not invalidated |
| Attested evidence | pipelock `SignPipelock`/`VerifyToolsList`; registry `auth.Method*`, `mcp-name:` tokens | Not mapped to a per-property ladder `lex<ann<obs<att` |
| `list_changed` maintenance | servers `everything/server/context.ts::toolsChanged`; pipelock drift epochs | No index, hypergraph and cache maintenance |
| Benchmark formats | LiveMCPBench `annotated_data/all_annotations.json` (`task_id, Question, Annotator Metadata.Tools`); MCPToolBench++ `data/<cat>/*.json` (`uuid, tools, mcp_tools_dict, function_call_label[step,id,mcp_server,similar_tools]`); ToolRet `queries/labels/relevance`; COLT BEIR files; MCPTox `pure_tool.json` + `response_all.json` (`server_name, tool_name, query, tool_content, security risk, paradigm`); AgentDojo `ground_truth` + injection `GOAL` | No benchmark gives effect or flow ground truth; TaaS keeps silver labels `J` separate |
| **Model-conditioned capability gap** | None. Nearest: ToolRet instruction-conditioned queries; HySet query-conditioned scoring; CaMeL quarantined LLM (`quarantined_llm.py`) | **No repo measures a per-class reliability profile of the deployed LLM** |
| **Provenance-sound eligibility** | None | **No repo filters retrieval by evidence strength** |
| **Set-level certificate** (S,C,P,E,L,V,M,B) | None | **No repo certifies a toolkit before execution** |
| Counterexample-guided refinement | Progent `generate_update_security_policy` (LLM updates from tool results); MCP-Zero repeated requests | Neither emits typed counterexamples; refinement is LLM-driven |

## (d) Reuse catalog

This repo has no root `LICENSE` file yet *(unverified whether intended)*. MIT and Apache-2.0 sources can flow into an MIT, Apache-2.0 or BSD release; Apache-2.0 additionally needs attribution and a NOTICE entry. Unlicensed code is all-rights-reserved by default.

**Already reused.** `data/raw/livemcpbench/` (`tools.json`, `all_annotations.json`, Apache-2.0) and `data/raw/mcptoolbenchpp/` (six category JSONs, MIT), pinned in `data/raw/SOURCES.txt` to commits `36a51a1` and `2bd35e5`. Both match the heads I cloned. `src/taas/baselines.py` re-implements `rag_topk` (RAG-MCP style) and `mcp_zero`; I did not check for code copying.

**Could reuse.**
- **MCP-Zero** `matcher.py` (MIT): exact server-then-tool scoring for a faithful baseline; keep the copyright header if any code is ported.
- **ToolRet** `trec_eval` (Apache-2.0): port `Comprehensiveness@k` with attribution. Its HF data is *unverified*.
- **COLT** and **MCPTox** (no license): reimplement `completeness` from the paper's definition. Use MCPTox only locally as an evaluation corpus and do not redistribute it. Its poisoned descriptions are hostile strings: never pass them to a tool-enabled agent, and treat them as inert test data.
- **AgentDojo** (MIT), **CaMeL** and **Progent** suites: banking/slack/workspace/travel tool lists plus `no_side_effect_tools` and always-allowed lists give independent effect labels for validating silver `J`. AgentDojo `ground_truth` and injection tasks could drive effect and flow-bound scenarios.
- **fides-gateway** `lattice.py` (MIT) and **CaMeL** `readers.py`/`sources.py` (Apache-2.0): cross-check `effects.join`/`label_rank` against an established product lattice.
- **Progent** `policy_analysis.py` (MIT): Z3 subset check for validating that declassification rules D only narrow a policy.
- **pipelock** `provenance/sign.go` (Apache-2.0): design reference for hashing the full tool object. This repo's `RawTool.definition_hash` (`data/registries.py`) covers name, description, inputSchema, outputSchema and annotations, but not `title`, `_meta` or extension fields, and truncates SHA-256 to 16 hex characters (64 bits). Consider covering all fields and using at least 128 bits.
- **registry** (Apache-2.0, mixed): `server.json` fields (`FileSHA256`, `Repository.ID`, publisher auth method) as a realistic `att` source, and `Status` for deprecation. Check per-file headers before copying.
- **servers** (mixed): use filesystem, git, memory and time as sandbox probe targets for `obs` evidence. `trigger-list-changed.ts` can drive Algorithm 3 tests.
- **HySet PoC** (MIT, third-party): optional set-level baseline. It needs training, and the underlying paper is a July 2026 preprint I only confirmed at abstract level.

## (e) How this repository differs

- **The unit is a certified toolkit, not a ranked list.** Every public system above returns top-k tools or a co-invocation set (HySet, COLT). TaaS returns a minimum-cost cover with typed sufficiency, consumability and producibility checks, effect and flow bounds, evidence, minimality and bridge ratio, and typed counterexamples.
- **The deployed model is part of the graph.** Class-typed model hyperedges with a measured reliability profile make the capability gap model-conditioned. No inspected repo conditions on the executing LLM's measured reliability.
- **Evidence strength gates eligibility before retrieval.** Annotations are treated as `ann`, below `obs` and `att`, with trust policies and a bitmap index. Existing code either trusts annotations (servers, fides-gateway) or enforces at call time (Progent, CaMeL).
- **Flow control is static and pre-execution.** CaMeL and FIDES track labels per runtime value; TaaS bounds flow over contracts, with declassification rules D, before anything runs.
- **Hash-bound maintenance.** pipelock and ETDI detect drift and re-approve. `Maintainer.on_list_changed` additionally restores `obs`/`att` evidence only for previously seen `(tool, hash)` pairs and invalidates cached toolkits exactly.
- **Honest gaps in this comparison.** I could not inspect RAG-MCP, Agent-as-a-Graph, MCPSHIELD or ScaleMCP implementations (no public code). Where TaaS claims superiority over them, the evidence is the papers' reported numbers, not code.
