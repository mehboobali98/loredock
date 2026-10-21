# Validation status

Reference host: Apple M3 Pro, 18 GB unified memory, macOS 26.3.1, ARM64. Application: AnythingLLM 1.18.0 at the committed immutable image digest. All published checks use the seven fictional Northstar documents. Company source documents and private validation evidence are excluded.

| Check | Observed result |
|---|---|
| Tooling | 22 unit tests, Ruff lint/format, and strict mypy pass; CI checks Python 3.10 and 3.13 |
| Initial import and repeat | Seven documents indexed; repeat import reports seven unchanged entries |
| Retrieval diagnostic | All expected document IDs found for 20/20 answerable and 5/5 ambiguous questions at top 4, threshold 0.25 |
| Restart | Registered document membership and Query settings persisted |
| Backup and restore | Successful restore of revision-2 ingestion state; seven document memberships, Query settings, API access, and a generated answer persisted; previous state retained |
| Isolated application routes | Local Ollama reachable, model-download route denied, external HTTPS unreachable |
| Initial full evaluation | Agent: 16/20 answerable, 5/5 unsupported, 2/5 ambiguous; 9/10 warm queries within 30 seconds; quality failed |
| Prompt revision evaluation | Agent: 17/20 answerable, 5/5 unsupported, 5/5 ambiguous; 10/10 warm queries within 30 seconds; quality failed |
| Corrected metadata and extractive policy configuration | Agent: 18/20 answerable, 5/5 unsupported, 4/5 ambiguous; zero critical policy errors; quality gate still failed |
| Final warm latency | 10/10 standard queries within 30 seconds; range 10.83–22.56 seconds |
| Final offline answers | All 30 questions completed on the isolated application network; no request errors |
| Replacement answer | Temporary fixture changed from 20 to 22 annual days; answer cites the replacement; old membership and original allowance clause absent from retrieval |
| Human acceptance | Pending human review of answers and returned passages |
| Company exports | Separate private workflow; no company validation evidence is published |

Evidence: [initial operations](../reports/public/operations.json), [final backup/restore and answer](../reports/public/operations-final.json), [replacement](../reports/public/replacement.json), [offline routes](../reports/public/offline-network.json), and [retrieval diagnostic](../reports/public/retrieval-only.json). Source retrieval is a diagnostic, not proof of factual correctness or passage support. The normal local network was restored after testing.

## Final measured run

[Read the final report](../reports/public/20261021T114957262249Z/evaluation.md), or inspect its [complete JSON](../reports/public/20261021T114957262249Z/evaluation.json). These are **agent assessments**, with all human reviews pending. Meeting the answerable and latency thresholds does not override the failed ambiguity gate.

All 15 policy questions preserved their tested conditions and had supporting sources. Three cases failed the unchanged rubric:

- **C03:** Correct activation priority and source, but omitted that this is strategic direction rather than a delivery commitment.
- **C05:** Correctly named both pilot measures, then added unsupported wording calling them “unresolved.” The unresolved item in the notes is the rollout date.
- **A03:** Surfaced both conflicting rollout targets and said neither was confirmed, but omitted the requested follow-up with Product and Engineering.

The median across all 30 requests was **16.38 seconds**; the maximum was **34.75 seconds** (C05). This median includes two fast application refusals without model generation. Latency measures complete synchronous responses, including retrieval and model reasoning, rather than first-token time. The first ten answerable questions define the standard latency sample; no later question replaces a slow or failed one.

Configuration: Ollama **0.40.6**, **Qwen3 8.2B Q4_K_M**, model digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, 8,192-token configured context, native MiniLM embeddings, LanceDB, Query mode, top four passages, 0.25 threshold, temperature 0.1, 1,000-character chunks with 20-character overlap. The report records image/model digests, embedding file hashes, prompts, ingestion revision, host details, and per-question evidence.

The direct Docker internal network blocked native-host access. Disabling masquerading did not block external HTTPS. The final offline override therefore isolates the application and uses a fixed-target relay for local inference plus a localhost-only application gateway. It leaves host connectivity unchanged and does not establish a host air gap. See [operations](operations.md).

Known limits include English text exports, one trusted operator, manual source freshness, synthetic benchmark coverage, and conversation history that can retain earlier passages. Start a fresh thread after policy changes. The first uploader incorrectly sent ISO dates where epoch milliseconds were required; ingestion revision 2 corrects this and places original source URLs in every chunk. Historical reports retain the observed processing-time fallback. Shared employee access and production capacity have not been validated.

Initial evidence: [baseline](../reports/public/20261021T103613527607Z/evaluation.md) and [prompt revision](../reports/public/20261021T105425344158Z/evaluation.md). These are agent judgments of final answers, not human acceptance. The unchanged suite exposed missing timing conditions, unsupported wording, and incorrect document labels. Corrections target source metadata and policy quotation behavior; model weights and retrieval settings remain unchanged. Final answers can still paraphrase despite quotation instructions, use inconsistent citation formatting, or omit a caveat. Prompt instructions do not enforce an extractive output contract.

Before claiming acceptance, obtain human review and resolve or explicitly revise the remaining quality requirements with that reviewer. Evaluate any proposed prompt/model change on the complete unchanged suite; add a separate held-out set before treating these tuning results as evidence of general quality. Private company validation and shared employee deployment remain separate milestones.
