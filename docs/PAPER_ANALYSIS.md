# Analysis of the paper's foundations and algorithms

**Paper.** M. Sellami and H. Mezni, *Tool-as-a-Service: Provenance-Aware Tool Discovery for LLM Agents in
Model Context Protocol Ecosystems*, IEEE Transactions on Services Computing (draft, 14 pp.).

This document is the planning and analysis stage of the paper-to-code pipeline: it restates every
formal object, checks each result, walks through the algorithms, records every place where the text
leaves a choice open (and the choice this implementation makes), and lists what the implementation
and the experiments taught us that bears on the manuscript. The code mapping is in §7.

---

## 1. Problem and contribution in one page

The paper reframes MCP tool discovery as **closing a capability gap**: given a prompt *x*, a principal's
policy Π, the executing model *m* and a registry snapshot, return either a toolkit *K* with a
**pre-execution certificate** *C*, or an explicit abstention with a typed counterexample χ. The toolkit
must be

* *functionally sufficient* for the goals the model cannot achieve alone,
* *interface-compatible* (through typing or through verified model bridges),
* *bounded* in reachable effects and information flows,
* *evidenced* at a required strength,
* of *minimum cost* (tool count, effect breadth, evidence confidence, tokens, declared QoS).

Three design commitments distinguish it from retrieval-only discovery (RAG-MCP, MCP-Zero, ScaleMCP,
graph retrievers):

1. **Model-conditioned composition** — the deployed model is itself a set of conditional, class-typed
   hyperedges with a measured reliability ρ_LLM; the gap Γ is computed, not assumed.
2. **Provenance-sound eligibility** — what a tool may do is established by evidence of stated
   strength (lex < ann < obs < att under the default trust policy), not by its description.
3. **Certification before execution, for any call order** — effects and flows are bounded over the
   whole toolkit before the model reads any tool output.

RQ1 (representation) → Defs 4–6; RQ2 (trust) → Props 1–2, Obs. 1, Lemma 1; RQ3 (composition) →
Def. 3, Eqs. 3–7, Alg. 2; RQ4 (evolution) → Prop. 3, Alg. 3.

---

## 2. Formal model (Sections 4–5)

| Object | Paper | Implementation choice |
|---|---|---|
| Semantic types Θ, <: | structural subtyping + small ontology (record, document, text, table, media, credential, identifier, location) + registry domain terms; κθ confidence | `types.py`: `kind[:domain][[]]`; kinds extended with structural kinds needed by real schemas (number, url, path, query, code, datetime, boolean, none); `kind:d <: kind`; `table:d <: record:d[]` |
| Effects E | `read(src)`, `write(r)`, `delete(r)`, `exec`, `egress(dst)`, `money`, `session`, scoped | `effects.py`: scope coverage by prefix/glob; `write(/reports/x)` ⊑ `write(/reports)` |
| Labels L, flow(t) | default join of input labels, narrowed by traces | `public < internal < private < secret`; join with the tool's source label |
| Contract c(t) (Def. 4) | (in, out, eff, flow, req, qos, srv, λ_t, h) | `contracts.py::CapabilityContract`; **every** field is used (see §7) |
| Provenance λ(t,a)=(π,σ,κ) | π ∈ {lex, ann, obs, att} | `provenance.py::ProvenanceRecord` |
| Trust policy θ_a | property-specific map to a totally ordered strength | `TrustPolicy`: lex .25, ann .50, obs .55+.20κ, att 1.0 (trusted signer) / .60 (unknown); lexical cues for delete/pay/exec trusted more |
| E_a^(ℓ) | bitmap over tool slots | `bitmap_index.py` (Python big-int bitmaps; live-slot bitmap for deletions) |
| Hypergraph H (Def. 5) | V=Θ, n-ary hyperedges, F (forbidden pairs), ∼ (substitution by head) | `hypergraph.py` |
| Model edges (Def. 6) | class-typed e_m^c with ρ_LLM(c, n, lang, ε, m) | `model_profile.py` + goal-instantiated `ModelEdge`s and bridges |
| Goal contract (Def. 1) | (in, out, eff⁺, σ, n, ε) + dependency order ≺ | `goals.py::GoalContract`, `GoalSpec` |
| Eligibility (Def. 2) | Elig = P^(ℓmin) ∩ V | `composer.py::eligible_set` (Eq. 3) or closed-world (Eq. 2) |
| Valid toolkit (Def. 3) | checks S, C, P, E, L, V (+ M, B recorded) | `certificate.py::certify` with witnesses |

---

## 3. The formal results — restatement and check

**Proposition 1 (evidence monotonicity).** ℓ ≤ ℓ′ ⇒ E_a^(ℓ′) ⊆ E_a^(ℓ) and B^(ℓ′) ⊆ B^(ℓ).
*Check.* Immediate from the threshold definition; holds for any trust policy because strength is a
total order. *Verified* by property-based test (`test_prop1_evidence_monotonicity`, 60 random registries).

**Proposition 2 (soundness of the two encodings).** (a) If E^(ℓ) is truthful for every a ∈ P, every
t ∈ P^(ℓ) truly has all of P; completeness is not needed. (b) CW_ℓ(C, F) excludes every truly violating
tool **iff** each such tool records some f′ ∈ F at level ℓ; truthfulness plays no role in (b).
*Check.* Both directions of (b) are correct as stated: a recorded violation is removed by Eq. (2), an
unrecorded one survives; note that (b) is about *safety* only — a false recorded violation removes a
safe tool (utility, not soundness), which the paper says. *Verified* by tests and empirically in E2:
`obs+` has **0** exposure at FAR = 0 for every attack fraction α.

**Observation 1 (MCP annotations).** "Missing hint ⇒ safe" is the closed-world encoding at ℓann and is
sound only if every non-read-only tool publishes a non-read-only hint; MCP's default (admit declared
read-only tools only) is the positive encoding with P = {readOnlyHint}, sound only if hints are
truthful. *Check.* Correct. E0 shows the premise of the closed-world reading fails on public
registries: 0 of 569 tools declare `readOnlyHint=false`, so the closed-world filter removes nothing.
E2 shows the positive reading is unsound under forgery: exposure 0.8% at α=0 rises to 52% at α=0.5.

**Lemma 1 (authorization as projection).** B_V^(ℓ) = B^(ℓ) ∩ V. *Check.* Holds because membership of a
tool depends only on its own assertions. *Verified*: 0 violations in 300 random trials (E7) and a
property test. Consequence used in the code: refinement excludes tools by shrinking V, never by
mutating the index.

**Proposition 3 (exact cache invalidation).** Inserting g changes Q^(ℓ) iff g asserts every a ∈ Q at
≥ ℓ; deleting g changes it iff g ∈ Q^(ℓ); a cached toolkit is stale iff a member is deleted/re-hashed,
an inserted eligible tool reaches a head type of K at lower cost, or the model/profile changes.
*Check.* The eligible-set part is exact. The toolkit clause is exact only for the *cost* component;
an inserted tool can also make a previously **abstained** request satisfiable, which the clause does
not cover (cached abstentions should be keyed and invalidated by the head types of their
counterexamples). *Verified* for eligible sets: over 9,600 (event × cache entry) pairs the cache was
invalidated iff the set changed — no false invalidations, no stale answers (E7).

**Property 1 (order independence of the effect and flow bounds).** If K satisfies (E), (L), (V) with
truthful evidence at ℓmin, no call sequence over K performs an effect outside A, a forbidden
combination, or a forbidden flow. *Check.* The **effect** part is sound: any sequence's effects are a
union of members' effects. The **flow** part depends on how (L) propagates labels. If labels are
propagated only along the reach graph recorded by the composition (the "derivation" reading suggested
by Fig. 3, where the revenue table is declassified by aggregation before egress), the claim fails: in
MCP every tool result returns to the model's context and the model can write any context content into
any text argument of an egress tool. E4 measures this directly — over ~43k simulated call sequences on
certified toolkits, **0** effect violations in both readings, but **≈17% of sequences realise a
forbidden flow under the derivation reading and 0% under the conservative reading** (context label =
join of everything read; every text-renderable argument, required or optional, can carry it). We
therefore implement the conservative reading as the default and recommend stating it in the paper.
Under it, the revenue scenario of Fig. 3 is not certifiable as one toolkit; the paper's own χ5
operator "split the task into two toolkits" repairs it (session 1: query → aggregate → write; session 2:
post from the hand-off labelled `internal`) — implemented in `refinement.py::split_on_flow`.

---

## 4. The algorithms

### Algorithm 1 — goal specification and gap analysis

Lines 1–2: pattern lookup in R, then the analyst LLM writes G in a fixed JSON schema (closed class
vocabulary, types from Θ, n_g, ε_g, σ). Lines 4–17 validate σ against the profile: a native claim is
refuted (→ data) if out(g) is not text-derivable, (→ effect) if eff⁺ ≠ ∅, (→ unreliable) if ρ < τ or n
exceeds the context budget; a non-native claim with ρ ≥ τ, derivable and effect-free is *challenged*
(shrink candidate Δ). Line 18 rejects cycles and unprovided inputs (CLARIFY). Γ = {g | σ(g) ≠ native}.
Cost: O(|G| · |≺|).

### Algorithm 2 — evidence-carrying toolkit discovery

1. Elig by bitmap intersection, O((|P|+1)⌈n/w⌉) word operations (E7: 4 µs at 10⁵ tools vs 133 ms
   for a scan).
2. Per gap goal, top-K eligible edges with H(e) <: out(g) by RRF of lexical, dense and structural
   scores (Eqs. 4–5, k0 = 60).
3. Backward closure (depth d, K per derived type) over tail types that are neither reachable nor
   model-coverable — this is what finds *intermediate* tools no goal names (E5: without closure only
   6% of synthetic chains are solved, with it 100%).
4. |T| ≤ Nmax: best-first branch-and-bound on Σcost; the first sufficient inclusion-minimal state
   popped is optimal because costs are positive. |T| > Nmax: constraint-aware greedy + minimality pass
   (no approximation claim, as the paper correctly notes).
5. Every expansion checks F (χ5), A (χ2), (L) (χ5), consumability and prerequisites (χ1).
6. Certificate with witnesses and the regime that produced K.

### Algorithm 3 — refinement (A) and maintenance (B)

(A) maps each failed check to one χ type and one operator, records refined specs as blocking clauses,
abstains after k iterations. (B) handles `list_changed` as delete-then-insert on a changed hash,
restores obs/att evidence only for (t, h) pairs seen before, and invalidates caches by Prop. 3.
E7: incremental update 31 ms vs 4.8 s full rebuild; a rug-pulled definition loses its obs evidence
(strength 0.73 → 0.25) and regains it only when reverted to the verified hash.

---

## 5. Ambiguities and the resolution adopted

| # | Where | Open point | Resolution in this code |
|---|---|---|---|
| A1 | §5 trust policy | numeric strengths of lex/ann/obs/att and how κ scales obs | lex .25, ann .50, obs .55+.20κ, att 1.0/.60 (trusted/unknown signer); thresholds ℓ = .25/.50/.65/.90 |
| A2 | Def. 3, Eq. 3 | vocabulary of properties P and F | positive: read_only, no_delete, no_exec, no_money, no_egress; negative: writes, deletes, execs, pays, egresses |
| A3 | Def. 2 | "every θ ∈ T(e) has a certain supertype in the set" | read as ∃σ ∈ R, σ <: θ (σ is a subtype of the tail); plus free parameters and recorded model bridges |
| A4 | Alg. 1 l. 8/15 | ctx holds only *native* outputs, so every native goal downstream of a data goal is demoted — contradicts §6.2 (g2–g4 stay native) | ctx holds the outputs of all predecessors (tool results return to context); `ctx_mode="literal"` kept as ablation (E6: toolkits grow from 1.42 to 1.93 tools) |
| A5 | Def. 3 (S) | a gap goal with a generic output type (`text`) is "reached" by the prompt's own text | a gap goal must be discharged by a type a **tool** produced |
| A6 | Def. 1 eff⁺ | analysts list access effects (`egress(web)` for a search) as well as purpose effects | effect goals are matched on purpose classes (write/delete/exec/money; egress only for `send`) |
| A7 | Eq. 6 | no relevance term: among type-compatible candidates the cheapest wins | optional w_rel·(1 − normalised retrieval score); w_rel = 0 is Eq. 6 (E3-tune/E6) |
| A8 | Def. 3 (L), Prop. 1 | label propagation along derivations vs whole context | conservative by default (Property 1 holds); derivation mode kept as ablation (E4) |
| A9 | §6.4 χ5 | semantics of "split the task into two toolkits" | two certified sessions; hand-off types carry the label session 1 assigns them |
| A10 | Def. 3 (C) | media outputs | consumable for a multimodal executor or when the tool writes an artefact |
| A11 | Def. 6 | class-typed edges with "tail sets of kinds" | instantiated per covered goal (Cov) plus format/extraction bridges with recorded ρ |
| A12 | §5 rule 2 | "extrapolated conservatively" | continue the last log-slope, else halve per decade |
| A13 | §5 rule 1 | "small n" | exact_n_max = 20 |
| A14 | §6.3 | greedy "best cost per newly covered requirement" | gain = newly reached goals + 0.5 × new types; node budget falls back to greedy |
| A15 | §6.1 | which tools are private sources | read effects on fs/db/memory/email, or observed private reads |
| A16 | §6.1 hash | which fields h(t) covers | SHA-256 over canonical JSON of the whole definition, 128 bits kept |
| A17 | §6.3/§6.4 | uncertain typing is "never treated as an exact match" | the χ1 repair may admit same-kind matches, flagged in the certificate's (S) witness |
| A18 | Table 1 | MCPToolBench++ request count | 1,509 requests (1,470 unique queries) in the public release vs 1,429 reported |

---

## 6. What the implementation and the experiments say about the paper

1. **The registry statistics replicate exactly** (E0): 76 servers, 569 tools, 44 annotated tools from
   three servers, all `readOnlyHint=true`, exactly one of them not read-only
   (`opgg-mcp::lol-summoner-renewal`), 7.7% kept by required hints. The share of state-modifying tools
   is 23.0% under LLM silver labels and 32.2% under the lexical labeller; the paper's 27.8% lies between,
   which suggests reporting the labelling method and its agreement with a reference.
2. **Provenance-sound eligibility works as claimed** (E2, H2) and the verifier's false-accept rate is
   the exposure knob (≈ linear).
3. **Certified toolkits remove out-of-scope injected actions** (E4, H4): 0 worst-case success vs
   3–8% for retrieval baselines and 100% for the full registry; effect bounds held in every simulated
   call order.
4. **Property 1 for flows needs the conservative reading of (L)** (see §3); state it.
5. **Gap analysis shrinks toolkits** (E3, H3): ~28% fewer tools than the no-gap ablation at equal
   recall. But on real registries the **set-level, type-checked cover has lower gold recall than
   per-subtask retrieval** (0.19 vs 0.25 on LiveMCPBench). The causes are measurable: in the
   attribution study, most misses are gold tools that *were* candidates but lost the minimum-cost
   choice, then type mismatches between independently produced type vocabularies (`record:trend[]` vs
   `record:book[]`), then retrieval budget. Recall also penalises inclusion-minimality where gold lists
   alternative tools (four trend sources for one goal).
6. **Eq. 6 needs a relevance term on real data.** Under pure Eq. 6, recall *falls* as the candidate
   budget grows (0.32 → 0.20 → 0.10 for K = 3/5/10 on the dev split) because a type-compatible tool
   with fewer effects always wins. Adding w_rel(1 − relevance) fixes this (E3-tune, E6: 0.08 → 0.19 on
   the test split).
7. **Rule 1 overrides real measurements.** Claude Sonnet summed 640 two-digit numbers exactly (4/4)
   by reading alone, Claude Haiku failed beyond n = 40; rule 1 still forbids native exact aggregation
   for both beyond n = 20. That is conservative by design; the paper could say the threshold is a
   policy parameter, not a capability claim.
8. **Strict rule 2 is costly without broad calibration.** Treating unmeasured classes (summarise,
   write, plan) as non-native enlarges toolkits from 1.42 to 1.92 tools at equal recall; the
   evaluation should state which classes were measured.
9. **Sanitised manifests remove description-borne injection** (E6): 60/60 poisoned descriptions
   reach the model in raw tool lists, 0/60 through the manifest, and tokens per tool fall 169 → 96.

---

## 7. Traceability: paper element → code → evidence

| Paper | Code | Test / experiment |
|---|---|---|
| Def. 1, Alg. 1 | `goals.py::GoalContract`, `parse_goal_spec`, `text_derivable`, `gap_analysis` | `test_reviews_large_n_moves_aggregation_into_gap`, E3, E6 |
| Def. 2, Eq. 3, Lemma 1 | `composer.py::eligible_set`, `bitmap_index.py::eligible_positive` | `test_lemma1_*`, E7 |
| Eq. 2, Prop. 2b | `bitmap_index.py::eligible_closed_world` | `test_prop2b_*`, E2 |
| Def. 3, Property 1 | `certificate.py::certify` | `test_property1_*`, E4 |
| Def. 4 | `contracts.py::CapabilityContract`, `extract_contract`, `make_contract` | E0 |
| Def. 5 (F, ∼, reach) | `hypergraph.py::Hypergraph`, `reach`, `flow_violations`, `substitutes` | scenarios, E4 |
| Def. 6, rules 1–4 | `model_profile.py::ModelProfile`, `isotonic_decreasing` | `test_rule1_*`, `test_unmeasured_*`, calibration |
| Prop. 1 | `provenance.py::TrustPolicy`, `bitmap_index.py` | `test_prop1_*` |
| Prop. 3 | `bitmap_index.py::insert/delete`, `maintenance.py::ToolkitCache` | `test_prop3_*`, E7 |
| Obs. 1 | `contracts.py::props_from_annotations` | `test_observation1_*`, E0, E2 |
| Eqs. 4–5 | `retrieval.py::structural_score`, `HybridRetriever` | E6-A |
| Eqs. 6–7 | `composer.py::CostModel`, `utility` | `test_branch_and_bound_matches_brute_force`, E5 |
| Alg. 2 | `composer.py::Composer.compose/_branch_and_bound/_greedy/candidates` | E3, E5 |
| Alg. 3A, χ1–χ5 | `refinement.py::refine`, `split_on_flow` | `test_revenue_conservative_needs_split`, E6 |
| Alg. 3B | `maintenance.py::Maintainer.on_list_changed` | `test_hash_binds_evidence_rug_pull`, E7 |
| Sanitised manifest, R | `manifest.py::sanitise`, `PatternRepository` | `test_sanitised_manifest_*`, E6-C |
| Analyst / assistant roles | `llm/backends.py` (replay, Anthropic, heuristic) | recorded in `data/llm_records/` |
| Figs. 1–3, Tables 5–6 | `scenarios.py` | `test_paper_scenarios_reproduce` (6 cases) |
