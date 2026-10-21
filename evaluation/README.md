# Evaluation protocol

The suite `northstar.jsonl` is versioned alongside the fictional corpus. Labels: P01–P15 policies, C01–C05 company context, U01–U05 unsupported, A01–A05 ambiguous/proposal/conflict. Each item has a workspace, question, expected source IDs, and a review rubric.

## What is measured

- Host wall-clock latency for a complete synchronous answer, including local HTTP, retrieval, and generation. This is not time to first token.
- Returned passages and source IDs; expected-source retrieval is a diagnostic, not a correctness grade.
- Runtime/model version, resolved model digest, context, and workspace settings.
- Each item uses a fresh session and Query mode. One warm-up request is excluded. The first ten answerable items define the standard warm-latency sample.

## Human review

Read the source fixture, question rubric, answer, and returned passages. For each item, record:

```json
{
  "P01": {
    "correct": true,
    "citations_supported": true,
    "behavior_satisfied": true,
    "critical_error": false,
    "notes": "States 20 days per calendar year; LD-LEAVE passage supports the claim."
  }
}
```

Keep annotations outside Git until a fictional-corpus report is explicitly exported. Apply with `review RUN.json ANNOTATIONS.json --reviewer human`. An agent doing the review must use `--reviewer agent`; this does not satisfy the human gate.

Correctness requires preserving material limits, dates, approvals, and exceptions. Citation support requires the returned evidence to establish substantive answer claims, not just a related document title. For unsupported questions, the assistant must avoid invented facts and acknowledge missing evidence. For ambiguity/conflict questions, it must surface the relevant distinction or uncertainty. An invented critical policy rule or omitted material condition is a critical error.

## Acceptance

- At least 18/20 answerable questions correct and supported.
- 5/5 unsupported questions appropriately refused.
- 5/5 ambiguity/proposal/conflict questions handled according to their rubric.
- No critical policy error.
- At least 8/10 standard warm questions within 30 seconds.
- Separately verify replacement, restart persistence, backup/restore, and ten offline questions after downloads.

Untested cases stay untested. Unreviewed cases stay pending. A small synthetic corpus does not establish broad model quality or capacity for 150 employees.
