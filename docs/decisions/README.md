# Decision records

Status: accepted for the initial laptop demo. These are requirements-based defaults; none claims a benchmark win over all alternatives.

| Choice | Requirement / evidence | Alternatives and tradeoff | Revisit when |
|---|---|---|---|
| Public generic repository; external private data | Portfolio reproducibility and confidential source separation | Private repository would make sharing simpler to control, but would not provide a public reproducible example | Company-specific deployment code or content cannot be generalized |
| AnythingLLM Docker | Existing browser UI, integrated RAG, and future workspace/user options | Desktop is simpler for one user; Open WebUI is another existing application. Docker adds a daemon and resource overhead | App retrieval, APIs, access controls, or maintenance no longer fit |
| Native Ollama | Existing provider integration; Apple Metal support; no cloud inference fees | MLX-LM and vLLM Metal merit hardware benchmarks; hosted APIs require funding and approved data handling | Measured answer latency or concurrency misses targets |
| Qwen3 8B Q4_K_M | Approx. 5.2 GB model download is plausible on an 18 GB Mac | Smaller models trade quality for resources; larger models need more memory. Actual correctness remains unproven until evaluation | Retrieved evidence is sufficient but model answers are inadequate |
| MiniLM native embedder | Integrated, local, English baseline with little setup | Larger local embedders may improve retrieval but need comparison and re-embedding | Expected documents/passages are missed after extraction/chunking checks |
| Embedded LanceDB | Upstream default; no extra database service | PostgreSQL + pgvector is attractive for SQL/relational integration; Qdrant for an independently operated retrieval service. Both add operations/integration work | Measured workload or integration requirements justify a service change |
| Manual exports first | No authenticated source connector is established; source extraction must be checked | Automated Google/Slack connectors reduce staleness but introduce authorization, deletion, and ACL synchronization | Demo usefulness is established and source ownership is agreed |
| Two workspaces and authority metadata | Current rules differ from historical announcements and strategy | One collection is easier to search across but increases policy/aspiration confusion | Cross-collection retrieval can preserve authority and permissions reliably |
| Query mode and explicit abstention | Evidence-based answers, independent evaluations | General chat and agents are more flexible but introduce additional behavior and tools | Separate user requirements and evaluation cover those capabilities |
| Start with 1,000/20 chunks, top 4, threshold 0.25 | Reproducible baseline close to upstream defaults | Other chunk sizes, overlap, thresholds, hybrid retrieval, and reranking may improve recall but need controlled comparisons | A diagnosed retrieval failure warrants one measured change |
| Python standard library CLI | Portable tooling without another package/service dependency | SDKs or a custom backend can help at greater integration complexity | Supported workflows exceed a small synchronous CLI |
| Human quality review, separate agent assessment | Correct source retrieval does not prove claim support | Model judges can scale assessment but have their own calibration and costs | A calibrated judge is validated against human labels |
| Defer n8n and persistent memory | Neither is required to validate document Q&A | n8n may orchestrate later sync; memory needs isolation, retention, and user controls | Those workflows have an explicit owner and acceptance tests |

## References

- [AnythingLLM Docker](https://docs.anythingllm.com/installation-docker/overview), [API](https://docs.anythingllm.com/features/api), [LanceDB integration](https://docs.anythingllm.com/setup/vector-database-configuration/local/lancedb), [native embedder](https://docs.anythingllm.com/setup/embedder-configuration/local/built-in).
- [Ollama hardware support](https://docs.ollama.com/gpu), [Qwen3 8B](https://ollama.com/library/qwen3:8b), [MLX-LM](https://github.com/ml-explore/mlx-lm), [vLLM Metal](https://docs.vllm.ai/projects/vllm-metal/en/stable/).
- [pgvector hybrid search](https://github.com/pgvector/pgvector#hybrid-search), [Qdrant distributed deployment](https://qdrant.tech/documentation/scaling/distributed_deployment/).
