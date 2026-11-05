# E3 — Independent operational-effect reference protocol

## 1. Purpose

E3 compares declared effects, metadata/lexical predictions, and independently observed effects. The experiment must not infer observed behavior from MCP annotations or from the prediction made by the method under evaluation.

## 2. Effect vocabulary

Use multi-label effects, not a forced binary read/write label:

- `read`: retrieve or inspect data without a demonstrated persistent change.
- `write`: create or modify persistent state.
- `delete`: remove or invalidate persistent state.
- `exec`: execute code, commands, workflows, or jobs.
- `egress`: transmit data to an external recipient or destination.
- `financial`: initiate or modify a financial transaction or paid resource.
- `permission_change`: modify identity, access, or security configuration.
- `unknown`: evidence is insufficient or the effect cannot be classified.

Effects may be multiple and context-dependent. A tool that reads and then sends data may have both `read` and `egress`.

## 3. MCP hints are declarations, not observations

Preserve `readOnlyHint`, `destructiveHint`, and `openWorldHint` as separate declared fields. In particular:

```text
readOnlyHint = false  DOES NOT imply  write
missing annotation   DOES NOT imply  read
destructiveHint      DOES NOT prove every invocation deletes
openWorldHint        DOES NOT specify the actual egress destination
```

The annotations baseline must output declaration values and uncertainty, not silently translate them into verified effects.

## 4. Independent observation

For each probeable tool:

1. Pin server image/revision, tool definition hash, configuration and environment.
2. Use synthetic, non-sensitive test data and disposable state.
3. Capture state snapshots before and after each invocation.
4. Capture network destinations, filesystem changes, database mutations, process/job events and returned values where applicable.
5. Record exact input, principal, policy, timestamp, trace and probe result.
6. Repeat probes where effects may be nondeterministic.
7. Have annotators classify the observed trace independently.
8. Adjudicate disagreements and preserve the original labels.

A tool is not classified as `read` merely because no state difference was observed in one probe. Report probe coverage and observability limitations.

## 5. Safety boundary

Never probe with real credentials, production data, external financial actions, destructive targets, or unbounded execution. Block egress by default unless the experiment specifically requires an isolated, controlled destination.

## 6. Reporting

Report per-effect precision/recall/F1, macro-F1, confusion matrices, unknown/abstention rate, probeable share, probe coverage, and inter-annotator agreement. Separate declared-versus-observed disagreement from classifier error.

## 7. Release gate

E3 remains `blocked` until independent traces and adjudicated effect references exist. Synthetic fixtures may test the pipeline but must be reported as unit tests, not empirical E3 results.
