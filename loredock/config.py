"""Configuration lives beside the checkout, never in it."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3:8b"
IMAGE = "mintplexlabs/anythingllm:1.18.0@sha256:5461782e7db41318a516925949a8f8366e258dd576411fca7961fe77dff054cc"


def inside(path, parent):
    return path.resolve() == parent.resolve() or parent.resolve() in path.resolve().parents


def home():
    path = Path(os.environ.get("LOREDOCK_HOME", str(ROOT.parent / "loredock-local"))).expanduser().resolve()
    if inside(path, ROOT) or path in ROOT.parents:
        raise ValueError("LOREDOCK_HOME must be outside the repository, in its own directory.")
    return path


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".loredock-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def settings():
    data = read_json(home() / "config.json", {})
    return {**data, "base_url": os.environ.get("LOREDOCK_BASE_URL", data.get("base_url", "http://127.0.0.1:3001")),
            "api_key": os.environ.get("LOREDOCK_API_KEY", data.get("api_key", ""))}


def initialize():
    if not (ROOT / "compose.yaml").is_file():
        raise ValueError("LoreDock needs its repository assets. Run from a clone or use an editable installation.")
    path = home()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    for name in ("storage", "runs", "backups", "logs", "models"):
        (path / name).mkdir(exist_ok=True, mode=0o700)
    if not (path / "config.json").exists():
        write_json(path / "config.json", {"base_url": "http://127.0.0.1:3001", "api_key": ""})
    return path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
