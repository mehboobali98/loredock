# Architecture

## Two data planes

The public checkout contains setup code, fictional knowledge, question rubrics, and explicitly exported fictional-corpus evidence. A separate runtime directory contains application state, local credentials, downloaded models, private exports, and raw reports.

AnythingLLM's storage bind mount persists its application database, document copies, embedding cache, and LanceDB index. That database is application state; LanceDB is a rebuildable search index. Original sources and the export manifest remain the content authority.

## Ingestion

1. Validate the manifest and UTF-8 `.md`/`.txt` files. Each document records an ID, title, source URL, owner, authority, and effective/version date. The export date can be recorded in the source text.
2. Create dedicated workspaces; do not adopt an unrelated existing workspace by its display name.
3. Hash source bytes. Skip unchanged, still-indexed documents.
4. Upload through `/api/v1/document/raw-text`, preserving provenance in both metadata and text.
5. Add embeddings and verify actual workspace document membership. HTTP 200 alone is insufficient: upstream may report embedding progress errors without failing the outer request.
6. For a changed file, verify the new version before withdrawing the old version. A successful run checks removal. This is not a transactional update across services; stop and investigate if an API operation fails.
7. Withdraw entries removed from the explicit manifest. Extracted files may remain on disk; this is removal from search, not guaranteed secure erasure of historical copies or backups.

The importer accepts readable exports, not arbitrary binary files. Images, tables, slide notes, and layout must be checked during export. The v1 importer does not claim a general PDF parser or authenticated Google Sites connector.

## Retrieval and generation

AnythingLLM performs native MiniLM embedding and LanceDB search. Both query and document embeddings use the same provider. Baseline: 1,000-character chunks, 20-character overlap, four returned passages, similarity threshold 0.25, model temperature 0.1, context 8,192 tokens.

The application connects to native Ollama through `host.docker.internal:11434`; the Python tools connect through host loopback. Running inference natively preserves access to Apple's GPU. The container's optional built-in model engine is disabled.

Query mode provides grounding and avoids normal rolling chat context. Each evaluation item additionally uses a fresh session ID. Model instructions request concise answers, citations, preserved exceptions, uncertainty, and no reasoning transcript. Qwen's `/no_think` instruction is a soft prompt control, not a general guarantee for other models.

Source cards show retrieved passages, not an automatic factual-support verdict. Evaluation reports retain returned passages so reviewers can judge each substantive claim.

## Boundaries

The single-operator application has no public listener. Its locally managed API key is stored outside Git. The Python client accepts only localhost HTTP origins, bypasses HTTP proxies, and rejects redirects. Do not expose this setup through a tunnel or reverse proxy as an employee service.

Memory/personalization is disabled. Query-mode workspaces do not use the default Agent mode. Do not enable tools, MCP servers, agents, cloud providers, or automatic source synchronization for this baseline.

## Reuse and scale

Another internal corpus can use its own manifest, authority rules, workspaces, and question suite. Private documents are never silently mixed into the public demo workspaces. Changing embedding models requires re-indexing; changing vector storage requires a supported adapter and validated migration. Provider configuration does not imply all implementations have the same filtering or retrieval behavior.

Production needs an always-on host, authentication, source ACL enforcement before generation, updates/deletions, backups, ownership, and load testing. Start with measured 1/5/10-request concurrency. Neither 150 accounts nor a large index alone proves a distributed database is needed. Multiple app containers sharing a folder do not establish safe horizontal scaling.
