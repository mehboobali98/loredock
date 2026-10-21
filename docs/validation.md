# Validation status

Reference host: Apple M3 Pro, 18 GB unified memory, macOS 26.3.1, ARM64. Application: AnythingLLM 1.18.0 at the committed immutable image digest. All checks use the seven fictional Northstar documents. No real employer documents have been imported.

| Check | Observed result |
|---|---|
| Tooling | 21 unit tests, Ruff lint/format, and strict mypy pass; CI checks Python 3.10 and 3.13 |
| Initial import and repeat | Seven documents indexed; repeat import reports seven unchanged entries |
| Retrieval diagnostic | All expected document IDs found for 20/20 answerable and 5/5 ambiguous questions at top 4, threshold 0.25 |
| Restart | Registered document membership and Query settings persisted |
| Backup and restore | Successful restore; seven document memberships and the local API key remained usable; previous state retained |
| Isolated application routes | Local Ollama reachable, model-download route denied, external HTTPS unreachable |
| Initial full evaluation | Agent: 16/20 answerable, 5/5 unsupported, 2/5 ambiguous; 9/10 warm queries within 30 seconds; quality failed |
| Prompt revision evaluation | Agent: 17/20 answerable, 5/5 unsupported, 5/5 ambiguous; 10/10 warm queries within 30 seconds; quality failed |
| Corrected metadata and extractive policy configuration | Focused checks complete; full evaluation pending |
| Replacement answer | Pending live generation; the CLI checks a separate 20-to-22-day fixture |
| Human acceptance | Pending human review of answers and returned passages |
| Company exports | Pending readable exports and private validation |

Evidence: [operations](../reports/public/operations.json), [offline routes](../reports/public/offline-network.json), and [retrieval diagnostic](../reports/public/retrieval-only.json). Source retrieval is a diagnostic, not proof of factual correctness or passage support. Restart/restore checks above establish state persistence; generation is checked separately.

The direct Docker internal network blocked native-host access. Disabling masquerading did not block external HTTPS. The final offline override therefore isolates the application and uses a fixed-target relay for local inference plus a localhost-only application gateway. It leaves host connectivity unchanged and does not establish a host air gap. See [operations](operations.md).

Known limits include English text exports, one trusted operator, manual source freshness, synthetic benchmark coverage, and conversation history that can retain earlier passages. Start a fresh thread after policy changes. The first uploader incorrectly sent ISO dates where epoch milliseconds were required; ingestion revision 2 corrects this and places original source URLs in every chunk. Historical reports retain the observed processing-time fallback. Shared employee access and production capacity have not been validated.

Initial evidence: [baseline](../reports/public/20261021T103613527607Z/evaluation.md) and [prompt revision](../reports/public/20261021T105425344158Z/evaluation.md). These are agent judgments of final answers, not human acceptance. The unchanged suite exposed missing timing conditions, unsupported wording, and incorrect document labels. Corrections target source metadata and policy quotation behavior; model weights and retrieval settings remain unchanged.
