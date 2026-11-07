# PaMCP E1 — conservative operation-evidence triage v0.3

**Status:** exploratory machine-generated candidates only; not reference labels, not adjudicated ground truth, not runtime verification, and not E1 completion.  
**Protocol:** PaMCP Definitive Experimental Specification v1.0; no protocol amendment.  
**Input:** 569-row `PaMCP_E1_AI_Semantic_Triage_v0.2.csv`.  
**Output:** `PaMCP_E1_AI_Semantic_Triage_v0.3.csv` (attached to the working conversation; raw CSV is not committed to the repository).  
**Output SHA-256:** `dc40fd3ef289f602631e5b7e5f946d63ac6111df437dc2ad2785858c7e1ec374`

## Why v0.3

The v0.2 review exposed over-assignment from broad matching across descriptions and schemas: financial-domain words in analyst recommendations, or mutation words in parameter descriptions/examples, were incorrectly treated as operation effects.

## Changes

- Restrict effect evidence to the tool operation name and first meaningful description line/sentence.
- Do not mine `Returns:`, `Args:`, `Parameters:`, `Example:`, or similar sections.
- Schema property names, descriptions, enum values, and examples cannot independently trigger an effect.
- Domain vocabulary does not imply a `money` effect unless a transaction is explicit.
- Context-dependent browser/session actions (click, fill, navigate, switch, reset, evaluate), egress-only notifications, Git branch checkout, and generic query execution abstain rather than being automatically labelled as state modification.
- Retrieval/computation wording without a qualifying effect is a provisional false candidate; ambiguity remains unresolved.
- Preserve the approved E1 construct: only `write`, `delete`, `exec`, and `money` count as non-read-only. `egress` and `session` alone do not.

This conservative rule set may increase abstention and miss indirect/conditional effects. It does not establish runtime behavior.

## Results (569 tools)

| Candidate status | v0.2 | v0.3 |
|---|---:|---:|
| Provisional true | 167 | 83 |
| Provisional false | 324 | 334 |
| Unresolved | 78 | 152 |
| **Total** | **569** | **569** |

This is not an accuracy improvement claim. The change reduces broad lexical over-assignment while increasing abstention.

## Check against the prior 69-case review

Of 17 cases previously marked CRITICAL for possible effect-class over-assignment, v0.3 yields 16 provisional false candidates and one unresolved case; none remains a provisional true candidate. This is a consistency check against a documentary review, not independent ground truth and not a precision estimate.

Examples reclassified from v0.2 positive candidates include `get_options`, `get_stock_price_date_range`, `get_text_file_contents`, `read_multiple_files`, `get_stock_fundamental`, `get_ticker_data`, `playwright_console_logs`, `playwright_get_visible_html`, `read_file`, `get_stock_ohlcv`, `read_process_output`, and `get_stock_market_cap`. `get_stock_trading_volume` remains unresolved.

## Tests and reproducibility

Eight unit tests cover retrieval over-assignment, domain/effect separation, explicit mutation wording, ambiguous browser/session operations, schema/example exclusion, Returns-section exclusion, egress/checkout handling, and generic query execution.

```bash
pytest -q tests/test_e1_ai_preannotation_v0_3.py
python -m taas.e1_ai_preannotation_v0_3 input.csv output.csv
```

The CSV preserves input columns and appends v0.3 candidate/evidence fields. Its raw bytes are attached to this conversation, not committed to the repository.

## Scientific gate

The candidates are for documentary-review prioritization only. They must not replace independent annotator labels or be used as adjudicated labels, E1 prevalence, accuracy, agreement, or downstream scientific outcomes. E1 remains blocked pending independent human reference annotation, agreement analysis, and adjudication. E2 and all E1-dependent experiments remain gated. No MCP server was executed in this pass.
