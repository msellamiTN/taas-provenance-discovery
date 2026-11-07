# E2 sampling design proposal — not frozen

**Status:** proposed_not_frozen  
**Protocol source:** E2 Human Annotation Protocol  
**Population snapshot:** E1 merged registry, 569 unique tool definitions  
**Proposed sample:** 120 tools  
**Proposed seed:** 20261107  
**Proposed sampling design:** proportional stratification by source × source category, with at least one tool sampled in every non-empty stratum

## Why 120 is proposed

For a finite population of \(N=569\), a conventional worst-case binary-proportion planning calculation with \(p=0.5\), 95% confidence (\(z=1.96\)), and an 8-percentage-point margin gives:

\[
n_0 = \frac{z^2p(1-p)}{e^2} \approx 150.06
\]

Applying the finite-population correction gives:

\[
n = \frac{Nn_0}{N-1+n_0} \approx 118.91
\]

The proposed sample is rounded up to 120. This is only a planning reference for an overall binary proportion under a simple-random-sampling approximation. It is **not** a power guarantee for semantic-type precision/recall, rare type classes, threshold-specific F1, or macro-F1.

## Strata and proposed allocation

The pinned registry has 12 non-empty source × category strata. The generated allocation is:

| Source | Category | Population tools | Proposed sample |
|---|---|---:|---:|
| LiveMCPTool | Code | 64 | 13 |
| LiveMCPTool | Discovery | 122 | 24 |
| LiveMCPTool | Entertainment | 43 | 9 |
| LiveMCPTool | File Access | 81 | 17 |
| LiveMCPTool | Finance | 31 | 7 |
| LiveMCPTool | Location | 12 | 3 |
| LiveMCPTool | Miscellaneous | 87 | 18 |
| LiveMCPTool | Visualization | 85 | 17 |
| MCPToolBench++ | finance | 1 | 1 |
| MCPToolBench++ | map | 32 | 7 |
| MCPToolBench++ | pay | 6 | 2 |
| MCPToolBench++ | search | 5 | 2 |
| **Total** | | **569** | **120** |

The generation script records actual sample IDs, per-stratum counts, registry SHA-256, annotation-unit count and output checksums. The two annotator sheets contain the same annotation units but independently shuffled order. The restricted ID mapping remains separate.

## Required safeguards before annotation

1. The study owner must explicitly accept or amend the proposed sample size, seed, and sampling design. Until then, the generated package remains a proposal and must not be distributed as a frozen annotation set.
2. Freeze the type matching rule over kind, domain and collection status; uncertainty and abstention handling; macro/micro averaging; confidence threshold treatment; and the statistical resampling unit.
3. Have two distinct human annotators work independently. They must not see model predictions, silver labels, each other's annotations, or the restricted ID mapping.
4. Report class-level support and uncertainty. Rare or absent semantic classes must not be silently omitted or treated as perfect.
5. The schema+probe-output condition remains unavailable until E3 supplies accepted hash-bound credential-free traces for the same sampled tools.

## Proposed package output

Preparation script: **experiments/e2/prepare_annotation_tasks.py**

Proposed invocation (do not run as a frozen annotation design until owner acceptance):

    python experiments/e2/prepare_annotation_tasks.py \
      --registry data/processed/registry_merged.json \
      --output artifacts/e2_annotation_proposal_20261107 \
      --sample-size 120 \
      --seed 20261107 \
      --sampling-design stratified_source_category

The resulting manifest must remain prepared_not_run with sample_design_status=proposed_not_frozen until owner acceptance. A prepared CSV is not an annotation result and does not change E2 status.
