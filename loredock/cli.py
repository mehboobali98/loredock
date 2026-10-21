import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .api import APIError, Client
from .config import ROOT, home, initialize, read_json, write_json
from .evaluate import (
    answer_text,
    apply_reviews,
    evaluate,
    export_public,
    load_suite,
    summarize,
)
from .ingest import (
    WORKSPACE_SETTINGS,
    ask,
    ingest,
    manifest,
    upload,
    workspace_documents,
)
from .models import JSONObject
from .runtime import (
    backup,
    client,
    compose,
    configure,
    model_pull,
    model_start,
    model_stop,
    offline,
    record_versions,
    restore,
    timestamp,
    verify_offline,
    wait_ready,
)

DEMO = ROOT / "examples/northstar/manifest.json"
SUITE = ROOT / "evaluation/northstar.jsonl"


def update_check(api: Client) -> None:
    data = manifest(DEMO)
    doc = data["documents"][0]
    slug = api.post(
        "/workspace/new",
        {
            "name": "LoreDock Update Check " + timestamp(),
            **WORKSPACE_SETTINGS,
        },
    )["workspace"]["slug"]
    try:
        old = upload(api, doc)
        api.post(f"/workspace/{slug}/update-embeddings", {"adds": old, "deletes": []})
        if not set(old) <= workspace_documents(api, slug):
            raise APIError("Original update-check fixture was not indexed.")
        doc = {
            **doc,
            "text": (ROOT / "examples/replacement/leave.md").read_text(),
            "date": "2026-10-15",
            "source_url": "https://github.com/mehboobali98/loredock/blob/main/examples/replacement/leave.md",
        }
        new = upload(api, doc)
        api.post(f"/workspace/{slug}/update-embeddings", {"adds": new, "deletes": []})
        if not set(new) <= workspace_documents(api, slug):
            raise APIError("Replacement fixture was not indexed.")
        api.post(f"/workspace/{slug}/update-embeddings", {"adds": [], "deletes": old})
        if workspace_documents(api, slug) != set(new):
            raise APIError("Old update-check fixture still present.")
        response = ask(
            api, slug, "How many days is the current annual paid leave allowance?"
        )
        search = api.post(
            f"/workspace/{slug}/vector-search",
            {
                "query": "How many annual paid leave days?",
                "topN": 100,
                "scoreThreshold": 0.0,
            },
        )
        serialized = json.dumps(
            [response.get("sources", []), search.get("results", [])]
        )
        result = {
            "checked_at": timestamp(),
            "old_document_membership_removed": True,
            "old_fixture_text_returned": "Full-time employees receive 20" in serialized,
            "answer": response["textResponse"],
            "sources": response.get("sources", []),
            "fixture_search_chunks": len(search.get("results", [])),
            "note": "Membership and returned-source checks are mechanical. Search covers up to 100 chunks in this tiny fixture; inspect the answer for 22 days.",
        }
        path = home() / "runs" / ("update-" + timestamp() + ".json")
        write_json(path, result)
        if result["old_fixture_text_returned"]:
            raise APIError("Superseded fixture text appeared in retrieval.")
        print(str(path))
    finally:
        api.request("DELETE", "/api/v1/workspace/" + slug)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="LoreDock — reproducible local knowledge RAG"
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in (
        "init",
        "up",
        "down",
        "logs",
        "configure",
        "doctor",
        "demo",
        "backup",
        "verify-update",
        "verify-offline",
    ):
        commands.add_parser(name)
    model = commands.add_parser("model")
    model.add_argument("action", choices=("start", "pull", "stop"))
    network = commands.add_parser("offline")
    network.add_argument("action", choices=("on", "off"))
    imp = commands.add_parser("ingest")
    imp.add_argument("--manifest", type=Path, default=DEMO)
    chat = commands.add_parser("ask")
    chat.add_argument(
        "workspace", help="Manifest workspace key, for example policies or context"
    )
    chat.add_argument("question")
    chat.add_argument("--corpus", default="northstar-demo")
    ev = commands.add_parser("eval")
    ev.add_argument("--manifest", type=Path, default=DEMO)
    ev.add_argument("--suite", type=Path, default=SUITE)
    ev.add_argument("--limit", type=int)
    ev.add_argument("--ids")
    report = commands.add_parser("report")
    report.add_argument("run", type=Path)
    review = commands.add_parser("review")
    review.add_argument("run", type=Path)
    review.add_argument("annotations", type=Path)
    review.add_argument("--reviewer", choices=("human", "agent"), required=True)
    export = commands.add_parser("export-public")
    export.add_argument("run", type=Path)
    rest = commands.add_parser("restore")
    rest.add_argument("archive", type=Path)
    rest.add_argument("--replace", action="store_true")
    return root


def run(args: argparse.Namespace) -> None:
    if args.command == "init":
        print(str(initialize()))
    elif args.command == "model":
        {"start": model_start, "pull": model_pull, "stop": model_stop}[args.action]()
    elif args.command == "offline":
        offline(args.action == "on")
    elif args.command == "up":
        initialize()
        compose("up", "-d", "--wait", "--wait-timeout", "240")
        print("Open http://127.0.0.1:3001")
    elif args.command == "down":
        compose("down")
    elif args.command == "logs":
        compose("logs", "--tail", "100")
    elif args.command == "configure":
        configure()
    elif args.command == "demo":
        initialize()
        model_pull()
        compose("up", "-d", "--wait", "--wait-timeout", "240")
        configure()
        ingest(client(timeout=900), DEMO)
        print(
            "Demo ready: http://127.0.0.1:3001 — select LoreDock Demo Policies or Company Context."
        )
    elif args.command == "ingest":
        ingest(client(timeout=900), args.manifest)
    elif args.command == "ask":
        state = read_json(home() / "ingestion.json", {}).get(args.corpus)
        if not state:
            raise ValueError("Ingest the corpus first.")
        response = ask(client(), state["workspaces"][args.workspace], args.question)
        print(answer_text(response["textResponse"]))
        print(
            "\nSources: "
            + ", ".join(
                source.get("title", "Untitled")
                for source in response.get("sources", [])
            )
        )
    elif args.command == "eval":
        if args.limit is not None and args.limit < 1:
            raise ValueError("--limit must be positive.")
        evaluate(client(), args.manifest, args.suite, args.limit, args.ids)
    elif args.command == "report":
        report = read_json(args.run)
        print(
            json.dumps(
                {"human": summarize(report), "agent": summarize(report, "agent")},
                indent=2,
            )
        )
    elif args.command == "review":
        print(
            json.dumps(
                apply_reviews(args.run, args.annotations, args.reviewer), indent=2
            )
        )
    elif args.command == "export-public":
        export_public(client(), args.run)
    elif args.command == "backup":
        backup()
    elif args.command == "restore":
        restore(args.archive, args.replace)
        wait_ready()
    elif args.command == "verify-update":
        update_check(client())
    elif args.command == "verify-offline":
        verify_offline()
    elif args.command == "doctor":
        checks: JSONObject = {
            "python": sys.version.split()[0],
            "data_directory": str(home()),
            "suite_questions": len(load_suite(SUITE)),
        }
        try:
            checks["runtime"] = record_versions()
        except (APIError, ValueError) as error:
            checks["ollama_error"] = str(error)
        try:
            current = client().get("/system")["settings"]
            checks["anythingllm"] = {
                key: current.get(key)
                for key in (
                    "LLMProvider",
                    "EmbeddingEngine",
                    "VectorDB",
                    "OllamaLLMModelPref",
                    "OllamaLLMTokenLimit",
                    "MemoryEnabled",
                    "MemoryAutoExtraction",
                )
            }
        except (APIError, ValueError) as error:
            checks["application_error"] = str(error)
        print(json.dumps(checks, indent=2))


def main(argv: list[str] | None = None) -> int:
    try:
        run(parser().parse_args(argv))
        return 0
    except KeyboardInterrupt:
        print(
            "LoreDock: interrupted. Downloads can resume with `model pull`; inspect pending imports before retrying.",
            file=sys.stderr,
        )
        return 130
    except (
        APIError,
        ValueError,
        RuntimeError,
        OSError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        print("LoreDock: " + str(error), file=sys.stderr)
        return 1
