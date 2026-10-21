# Operations

## Start and stop

```bash
python3 -m loredock model start
python3 -m loredock up
python3 -m loredock doctor

python3 -m loredock down
python3 -m loredock model stop
```

The model-stop command only signals a recorded LoreDock-owned Ollama process after checking its command. If another Ollama server already owns port 11434, LoreDock reuses it and does not claim control over its network/cloud settings or stop it. Inspect those settings yourself, or stop that server through its normal owner before starting LoreDock's managed server. Restart the managed server with `model start` after reboot; Docker's restart policy only covers the application.

The app listens on `127.0.0.1:3001`; the managed model server listens on `127.0.0.1:11434`. No tunnel or public deployment is provided. Docker must be running. On Linux, host-network reachability of a loopback-only native model server differs from Docker Desktop; the verified reference deployment is macOS.

## Back up and restore

```bash
python3 -m loredock backup
# The returned archive is private and includes application credentials.
python3 -m loredock restore /absolute/path/to/BACKUP.tar.gz --replace
python3 -m loredock doctor
```

Backup stops the application before archiving its storage, persisted `server.env`, local configuration, ingestion inventory, and version record; it restarts the app afterward. Archives are mode 0600 but **not encrypted**. Store them only in an appropriate private location. Ollama model weights, logs, and evaluation runs are not included. The application storage includes native embedding caches.

Restore validates archive paths and disallows links/special files, stages the contents, stops the app, and retains the previous state in an external recovery folder. It never deliberately deletes the old storage. If interrupted during a restore, keep the app stopped and inspect that recovery folder before retrying. Use the same pinned application image for the first restore test.

Do not run import/evaluation during backup or restore. This is a single-operator workflow, not an online production backup design. Model weights must still be present for offline generation.

## Update documents

Edit the source export and its manifest date/authority, then rerun:

```bash
python3 -m loredock ingest --manifest /absolute/path/to/manifest.json
python3 -m loredock verify-update
```

Unchanged indexed documents are skipped. A processing-format revision also triggers replacement, so corrected metadata is applied without editing the source files. Changed documents are uploaded/embedded and checked before old memberships are removed. Entries deleted from the manifest are withdrawn from their registered workspace. API errors are not atomic transactions; inspect state and workspace membership after interruption. Withdrawing a source does not erase historical chats, extracted files, archives, or other workspaces. Start a new thread after updates: upstream can backfill earlier source passages from the current conversation, even in Query mode. Replacement checks and evaluations use fresh sessions.

## Offline check

After successful downloads and ingestion, `python3 -m loredock offline on` isolates the application on a Docker internal network. A fixed-target relay, using the already pinned application image's Node runtime, bridges only native Ollama inference/inspection endpoints. Pull, push, and other management routes are denied. The relay has no published port; no new container image is needed. This leaves the host's connectivity unchanged and does not establish a host air gap.

Run `python3 -m loredock verify-offline` to check from the application container that external HTTPS fails, `http://ollama-relay:11434/api/version` succeeds, and model downloads are denied. Then run ten questions with `python3 -m loredock eval --limit 10`. Restore normal networking with `python3 -m loredock offline off`. The managed native Ollama server has cloud features disabled; use downloaded local weights. A preexisting server requires its owner's configuration check.

During isolation, the relay also provides a fixed application gateway at `127.0.0.1:3001`, because Docker Desktop blocked direct host access to the internal app's published port. It forwards only to the local application, never a request-selected host. Agent WebSockets and shared use are outside this test transport's scope.

Direct native-host access failed on the reference Docker Desktop internal network, which motivated the relay. If local inference still becomes unreachable, restore normal networking and record the check as failed. Do not claim offline verification merely because a warm query worked with unrestricted application internet access.

## Update software and models

1. Back up, record the current image digest/model digest, and review upstream release notes.
2. Change the pinned release and immutable manifest digest together in `compose.yaml`, `compose.offline.yaml`, and `loredock/config.py`.
3. Start the new application against a copy of private storage first; migrations may affect rollback.
4. Rerun tooling tests, ingestion checks, the same question suite, replacement, persistence, and restore checks.
5. Publish measured differences and unresolved failures. Do not silently overwrite a benchmark from another configuration.

`model pull` records the resolved model digest because model tags can change. Reproducing historical model results requires retaining that model blob or obtaining the same digest, not merely pulling the same tag later. Changing embedding providers requires rebuilding the index and rechecking retrieval.

## Troubleshoot

- Docker socket unavailable: start Docker Desktop and wait until it is ready.
- Port occupied: identify the existing service before changing or stopping it. The reference app uses port 3001.
- App cannot reach Ollama: verify host `127.0.0.1:11434/api/version`, then inspect access to `host.docker.internal:11434` from the container. Do not casually bind the model to all interfaces.
- First embedding fails: check app logs and outbound access for the initial weight download; rerun ingest after fixing the cause. LoreDock checks actual document membership.
- A model transfer stalls: interrupt `model pull` and retry it to resume Ollama's saved progress. The CLI reports streamed transferred-byte progress, not allocated disk space. Partial model files are not proof of a successful download; Ollama verifies the final digest.
- Incorrect answer: inspect extracted text, retrieved passages, authority/date metadata, then model behavior. Change one retrieval setting at a time and rerun the same suite.
- API key invalid: create a new key under AnythingLLM Developer API, set `LOREDOCK_API_KEY` locally, and revoke obsolete keys through the UI. Never put it in a command screenshot or committed file.
