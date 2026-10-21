"""Local process lifecycle, version recording, and quiesced backups."""
import json
import os
import platform
import shutil
import signal
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from .api import Client, APIError
from .config import ROOT, IMAGE, MODEL, home, initialize, read_json, settings, sha256, write_json


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def compose(*args, capture=False):
    env = {**os.environ, "LOREDOCK_STORAGE": str(home() / "storage"), "LOREDOCK_ENV_FILE": str(home() / "server.env")}
    files = ["-f", str(ROOT / "compose.yaml")]
    if (home() / "offline.enabled").exists():
        files += ["-f", str(ROOT / "compose.offline.yaml")]
    return subprocess.run(["docker", "compose", *files, *args],
                          env=env, check=True, text=True, capture_output=capture)


def client():
    config = settings()
    return Client(config["base_url"], config["api_key"])


def wait_ready(seconds=180):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            client().request("GET", "/api/ping", auth=False)
            return
        except APIError:
            time.sleep(2)
    raise RuntimeError("AnythingLLM did not become ready. Run `python3 -m loredock logs`.")


def offline(enabled):
    """Recreate only the project network; never change the host's internet access."""
    initialize()
    compose("down")
    marker = home() / "offline.enabled"
    if enabled:
        marker.write_text("Docker internal network enabled\n")
    elif marker.exists():
        marker.unlink()
    compose("up", "-d", "--wait", "--wait-timeout", "240")
    print("Internal network enabled. Verify external access fails and local model access succeeds." if enabled else "Normal project network restored.")


def model_start():
    initialize()
    ollama = Client("http://127.0.0.1:11434")
    try:
        ollama.request("GET", "/api/version", auth=False)
        print("Ollama is already running; its listener and cloud settings are managed by its existing owner.")
        return
    except APIError:
        pass
    binary = shutil.which("ollama")
    if not binary:
        raise RuntimeError("Install native Ollama first: brew install ollama (macOS), or https://ollama.com/download.")
    env = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(home() / "models"),
           "OLLAMA_NO_CLOUD": "1", "OLLAMA_CONTEXT_LENGTH": "8192", "OLLAMA_NUM_PARALLEL": "1",
           "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_FLASH_ATTENTION": "1"}
    with (home() / "logs/ollama.log").open("ab") as log:
        process = subprocess.Popen([binary, "serve"], env=env, stdout=log, stderr=log, start_new_session=True)
    write_json(home() / "ollama-process.json", {"pid": process.pid})
    for _ in range(30):
        try:
            ollama.request("GET", "/api/version", auth=False)
            print("Ollama is listening on 127.0.0.1:11434.")
            return
        except APIError:
            if process.poll() is not None:
                raise RuntimeError("Ollama exited. Inspect the private ollama.log.")
            time.sleep(1)
    raise RuntimeError("Ollama startup timed out. Inspect the private ollama.log.")


def model_stop():
    path = home() / "ollama-process.json"
    state = read_json(path, {})
    pid = state.get("pid")
    if not pid:
        raise RuntimeError("No LoreDock-managed Ollama process recorded; leave other servers untouched.")
    process = subprocess.run(["ps", "-p", str(pid), "-o", "command="], text=True, capture_output=True)
    if "ollama serve" not in process.stdout:
        raise RuntimeError("Recorded process is absent or no longer Ollama; refusing to signal it.")
    os.kill(pid, signal.SIGTERM)
    path.unlink()
    print("Stopped LoreDock's Ollama server.")


def model_pull():
    model_start()
    print("Downloading/verifying qwen3:8b (approximately 5.2 GB on first use)...", flush=True)
    Client("http://127.0.0.1:11434", timeout=3600).request("POST", "/api/pull", {"model": MODEL, "stream": False}, auth=False)
    record_versions()


def record_versions():
    ollama = Client("http://127.0.0.1:11434")
    version = ollama.request("GET", "/api/version", auth=False)
    tags = ollama.request("GET", "/api/tags", auth=False)
    model = next((item for item in tags.get("models", []) if item.get("name") == MODEL), None)
    record = {"recorded_at": timestamp(), "anythingllm_image": IMAGE, "ollama_version": version.get("version"),
              "model": model, "context_tokens": 8192, "embedding_model": "Xenova/all-MiniLM-L6-v2",
              "embedding_provider": "native", "vector_database": "lancedb"}
    record["host"] = {"os": platform.system(), "release": platform.release(), "architecture": platform.machine(),
                      "logical_cpus": os.cpu_count()}
    cache = home() / "storage/models/Xenova/all-MiniLM-L6-v2"
    record["embedding_file_hashes"] = {str(path.relative_to(cache)): sha256(path) for path in sorted(cache.rglob("*")) if path.is_file()}
    if settings().get("api_key"):
        try:
            labels = "text_splitter_chunk_size,text_splitter_chunk_overlap,memory_enabled,memory_auto_extraction,default_agent_skills,disabled_agent_skills"
            record["application_preferences"] = client().request("GET", "/api/admin/system-preferences-for?labels=" + labels, auth=False)
        except APIError:
            record["application_preferences"] = "unavailable; inspect UI preferences"
    write_json(home() / "versions.json", record)
    return record


def configure():
    initialize()
    wait_ready()
    api = client()
    if not api.api_key:
        result = api.request("POST", "/api/system/generate-api-key", {"name": "LoreDock local tooling"}, auth=False)
        secret = (result.get("apiKey") or {}).get("secret")
        if not secret:
            raise RuntimeError("Generate a key in AnythingLLM Developer API settings and set LOREDOCK_API_KEY.")
        stored = read_json(home() / "config.json", {})
        stored["api_key"] = secret
        write_json(home() / "config.json", stored)
        api = client()
    current = api.get("/system").get("settings", {})
    if current.get("EmbeddingEngine") not in (None, "native"):
        raise RuntimeError("Existing instance uses another embedding provider; use a fresh LOREDOCK_HOME.")
    api.post("/system/update-env", {"LLMProvider": "ollama", "OllamaLLMBasePath": "http://host.docker.internal:11434",
             "OllamaLLMModelPref": MODEL, "OllamaLLMTokenLimit": 8192,
             "EmbeddingModelMaxChunkLength": 1000})
    # Local single-operator UI endpoint. In password/multi-user mode, configure these in the UI instead.
    api.request("POST", "/api/admin/system-preferences", {
        "text_splitter_chunk_size": 1000, "text_splitter_chunk_overlap": 20,
        "memory_enabled": False, "memory_auto_extraction": False,
        "default_agent_skills": "", "disabled_agent_skills": "rag-memory,document-summarizer,web-scraping,web-browsing",
        "agent_clarifying_questions_enabled": False,
        "custom_app_name": "LoreDock", "meta_page_title": "LoreDock — private knowledge"}, auth=False)
    api.request("POST", "/api/onboarding", {}, auth=False, expect_json=False)
    applied = api.get("/system")["settings"]
    if applied.get("MemoryEnabled") or applied.get("MemoryAutoExtraction"):
        raise RuntimeError("Memory settings were not disabled; inspect UI preferences.")
    print("Local providers, chunking, and memory settings configured. Application key saved outside Git.")
    return record_versions()


def backup():
    initialize()
    target = home() / "backups" / (timestamp() + ".tar.gz")
    compose("stop")
    try:
        with target.open("xb") as stream:
            os.chmod(target, 0o600)
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                for name in ("storage", "server.env", "config.json", "ingestion.json", "versions.json"):
                    path = home() / name
                    if path.exists():
                        archive.add(path, arcname=name)
    finally:
        compose("start")
    print(str(target))
    return target


def safe_extract(archive, destination):
    """Reject links, path traversal, devices, and unexpected top-level entries."""
    destination = Path(destination).resolve()
    allowed = {"storage", "server.env", "config.json", "ingestion.json", "versions.json"}
    members = archive.getmembers()
    for member in members:
        path = Path(member.name)
        if (path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in allowed
                or not (member.isfile() or member.isdir())):
            raise ValueError("Unsafe or unsupported backup archive member.")
    for member in members:
        path = destination / member.name
        if member.isdir():
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, path.open("xb") as target:
                shutil.copyfileobj(source, target)
            path.chmod(0o600)


def restore(path, replace=False):
    initialize()
    storage = home() / "storage"
    if any(storage.iterdir()) and not replace:
        raise ValueError("Storage is not empty. Use --replace to retain it in a recovery folder and restore the backup.")
    staged = home() / ("restore-" + timestamp())
    staged.mkdir(mode=0o700)
    with tarfile.open(Path(path).expanduser(), "r:gz") as archive:
        safe_extract(archive, staged)
    if not (staged / "storage").is_dir():
        raise ValueError("Backup contains no storage directory.")
    compose("stop")
    recovery = home() / ("before-restore-" + timestamp())
    recovery.mkdir(mode=0o700)
    try:
        for name in ("storage", "server.env", "config.json", "ingestion.json", "versions.json"):
            existing = home() / name
            if existing.exists():
                existing.rename(recovery / name)
            if (staged / name).exists():
                (staged / name).rename(existing)
    except Exception:
        for item in recovery.iterdir():
            if not (home() / item.name).exists():
                item.rename(home() / item.name)
        raise
    finally:
        compose("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "240")
    print("Restored. Previous state retained at " + str(recovery))
    return recovery
