# Phase 2: Semantic enrichment

## Design

For each of the 569 MCP tool definitions, create two independent annotations: capability semantics and operational security. Each annotation is generated in a fresh GPT session. Eight deterministic work shards balance 1,138 tasks. Sessions must not see benchmark task queries, gold tool mappings, existing silver labels, or other annotators' outputs.

## Generate

~~~bash
python scripts/create_semantic_annotation_workpacks.py --outdir results/runs/semantic-annotation-run01 --workers 8
~~~

Outputs: worker_01.jsonl through worker_08.jsonl and workpack_manifest.json. The generator reads only the registry array, records the registry SHA-256 and tool-definition fingerprints, and refuses to overwrite a non-empty output directory.

## Run sessions

For each shard, start a fresh independent GPT session. Supply GPT_SESSION_PROTOCOL.md, annotation.schema.json, and only that shard. Return one JSON object per task as JSONL. Record actual session ID, model ID, prompt hash, workpack hash, timestamps, and output hash. Keep the two annotation perspectives independent.

The generator does not invoke GPT or create sessions. An authenticated GPT session/API runner is still required for that step.

## Validate

~~~bash
python scripts/validate_semantic_annotations.py --workpack-dir results/runs/semantic-annotation-run01 --annotations results/runs/semantic-annotation-run01/annotations/worker_01.jsonl results/runs/semantic-annotation-run01/annotations/worker_02.jsonl --report results/runs/semantic-annotation-run01/validation_report.json
~~~

The validator checks task and tool identity, definition hash, perspective, required fields, confidence bounds, allowed operation classes, and verbatim evidence spans. It reports missing tasks, duplicates, mismatches, and primary-capability disagreements. It does not treat structural validity as proof that an annotation is true.

## Enriched hypergraph

After validation and blind adjudication, add capability-concept vertices, domain vertices, argument/output semantic types, and provenance links to each annotation. Keep LLM-inferred effects separate from observed runtime effects. Preserve confidence, uncertainty, source session/model, exact evidence spans, and definition hash. Never use benchmark gold labels to create these semantic annotations.

## Evaluation

Compare the 31-type deterministic baseline with the enriched graph using Recall@k, Precision@k, MRR, nDCG, composition exact match, set precision/recall, inter-annotator agreement, adjudication rate, evidence-span validity, and calibration. Report LiveMCPBench and MCPToolBench++ separately because their task structures differ.

## Status

This phase currently provides workpack generation, schema, session protocol, and validation scaffolding. GPT annotation, adjudication, and enriched graph construction have not yet been executed.