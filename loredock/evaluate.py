"""Reproducible measurements; correctness remains an explicit review judgment."""
import json
import html
import re
import shutil
import time
from pathlib import Path
from .config import ROOT, home, inside, read_json, sha256, write_json
from .ingest import ask, manifest, verify_corpus
from .runtime import record_versions, timestamp


def load_suite(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = set()
    for row in rows:
        if row["id"] in ids or row["kind"] not in ("answerable", "unsupported", "ambiguous"):
            raise ValueError("Duplicate ID or unsupported question kind.")
        if not row.get("question") or not row.get("rubric") or not isinstance(row.get("expected_sources"), list):
            raise ValueError("Questions require question, rubric, and expected_sources.")
        ids.add(row["id"])
    if not rows:
        raise ValueError("Evaluation suite is empty.")
    return rows


def source_ids(sources):
    return sorted(set(re.findall(r"\bLD-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", json.dumps(sources, ensure_ascii=False))))


def summarize(report, reviewer="human"):
    rows = report["results"]
    totals = {kind: sum(row["kind"] == kind for row in rows) for kind in ("answerable", "unsupported", "ambiguous")}
    reviewed = [row for row in rows if row.get("reviews", {}).get(reviewer)]
    passes = {kind: 0 for kind in totals}
    for row in reviewed:
        review = row["reviews"][reviewer]
        passed = review["correct"] and review["behavior_satisfied"] and not row.get("error")
        if row["kind"] == "answerable":
            passed = passed and review["citations_supported"]
        if passed:
            passes[row["kind"]] += 1
    standard = [row for row in rows if row["kind"] == "answerable"][:10]
    timings = [row["latency_seconds"] for row in standard if not row.get("error")]
    complete_baseline = totals == {"answerable": 20, "unsupported": 5, "ambiguous": 5}
    quality_pass = (len(reviewed) == len(rows) and complete_baseline and passes["answerable"] >= 18
                    and passes["unsupported"] == 5 and passes["ambiguous"] == 5
                    and all(not row["reviews"][reviewer].get("critical_error", False) for row in reviewed))
    return {"reviewer_kind": reviewer, "reviewed": len(reviewed), "total": len(rows), "totals": totals,
            "passes": passes, "errors": sum(bool(row.get("error")) for row in rows),
            "quality_gate": "pass" if quality_pass else ("pending" if len(reviewed) < len(rows) else "fail"),
            "standard_warm_questions": len(standard), "within_30_seconds": sum(value <= 30 for value in timings),
            "latency_gate": "pass" if report.get("warmup_completed") and len(standard) == 10 and sum(value <= 30 for value in timings) >= 8 else "fail"}


def markdown(report):
    human = summarize(report)
    agent = summarize(report, "agent")
    lines = ["# LoreDock evaluation", "", f"Run: `{report['id']}`", "",
             f"Classification: **{report['classification']}**. Human quality gate: **{human['quality_gate']}**.",
             "Correctness and support are review judgments; retrieving an expected document alone does not prove either.", "",
             f"Human-reviewed: {human['reviewed']}/{human['total']}. Agent-reviewed: {agent['reviewed']}/{agent['total']}.",
             f"Warm latency: {human['within_30_seconds']}/{human['standard_warm_questions']} standard questions within 30 seconds.",
             f"Request errors: {human['errors']}.", "", "## Configuration", "", "```json",
             json.dumps(report["configuration"], indent=2, ensure_ascii=False), "```", "", "## Results", "",
             "| ID | Kind | Seconds | Retrieved expected source | Agent review | Human review |",
             "|---|---|---:|---|---|---|"]
    for row in report["results"]:
        review = row.get("reviews", {}).get("human")
        status = "pending" if not review else ("pass" if review["correct"] and review["behavior_satisfied"]
                     and (row["kind"] != "answerable" or review["citations_supported"]) else "fail")
        assessed = row.get("reviews", {}).get("agent")
        agent_status = "pending" if not assessed else ("pass" if assessed["correct"] and assessed["behavior_satisfied"]
                     and (row["kind"] != "answerable" or assessed["citations_supported"]) else "fail")
        lines.append(f"| {row['id']} | {row['kind']} | {row['latency_seconds']:.2f} | {row['expected_source_retrieved']} | {agent_status} | {status} |")
    lines += ["", "## Answers and review rubrics", ""]
    for row in report["results"]:
        lines += ["### " + row["id"], "", row["question"], "", "**Expected behavior:** " + row["rubric"], "",
                  "**Answer:**", "", row.get("answer") or "(No answer; request failed.)", "",
                  "**Returned source IDs:** " + ", ".join(row["retrieved_source_ids"]), ""]
        if row.get("sources"):
            lines += ["<details><summary>Returned passages for support review</summary>", ""]
            for source in row["sources"]:
                lines += ["**" + html.escape(source.get("title", "Untitled source")) + "**", "",
                          "<pre>" + html.escape(source.get("text", source.get("chunk", "No passage returned."))) + "</pre>", ""]
            lines += ["</details>", ""]
        for kind, review in row.get("reviews", {}).items():
            lines += [f"**{kind.capitalize()} assessment:** {review.get('notes', '')}", ""]
    return "\n".join(lines) + "\n"


def save_report(path, report):
    write_json(path, report)
    Path(path).with_suffix(".md").write_text(markdown(report), encoding="utf-8")


def evaluate(client, manifest_path, suite_path, limit=None, ids=None):
    data = manifest(manifest_path)
    state = read_json(home() / "ingestion.json", {}).get(data["id"])
    if not state:
        raise ValueError("Ingest this manifest first.")
    verify_corpus(client, data, state)
    rows = load_suite(suite_path)
    if ids:
        wanted = set(ids.split(","))
        if not wanted <= {row["id"] for row in rows}:
            raise ValueError("Unknown question ID.")
        rows = [row for row in rows if row["id"] in wanted]
    if limit:
        rows = rows[:limit]
    configuration = record_versions()
    configuration["workspaces"] = {key: {field: client.workspace(slug).get(field) for field in
        ("chatMode", "chatProvider", "chatModel", "topN", "similarityThreshold", "openAiTemp", "openAiPrompt")}
        for key, slug in state["workspaces"].items()}
    report = {"id": timestamp(), "classification": data["classification"], "corpus_id": data["id"],
              "manifest_sha256": sha256(manifest_path), "suite_sha256": sha256(suite_path),
              "document_hashes": {doc["id"]: doc["sha256"] for doc in data["documents"]},
              "configuration": configuration, "results": []}
    run_path = home() / "runs" / (report["id"] + ".json")
    first = rows[0]
    print("Warming the answer model (excluded from measured results)...", flush=True)
    ask(client, state["workspaces"][first["workspace"]], first["question"])
    report["warmup_completed"] = True
    for row in rows:
        print("Evaluating " + row["id"] + "...", flush=True)
        started = time.perf_counter()
        answer, sources, error = "", [], None
        try:
            response = ask(client, state["workspaces"][row["workspace"]], row["question"])
            answer, sources = response["textResponse"], response.get("sources", [])
        except Exception as exc:
            error = type(exc).__name__
        retrieved = source_ids(sources)
        report["results"].append({**row, "latency_seconds": round(time.perf_counter() - started, 4),
            "answer": answer, "sources": sources, "retrieved_source_ids": retrieved,
            "expected_source_retrieved": bool(set(row["expected_sources"]) & set(retrieved)),
            "inline_source_ids": source_ids([answer]), "error": error, "reviews": {}})
        save_report(run_path, report)
    verify_corpus(client, data, state)
    print(str(run_path))
    return run_path


def apply_reviews(run_path, review_path, reviewer):
    if inside(Path(run_path), ROOT):
        raise ValueError("Review the private runtime report, then export a public copy explicitly.")
    report = read_json(run_path)
    reviews = read_json(review_path)
    rows = {row["id"]: row for row in report["results"]}
    if not isinstance(reviews, dict) or not set(reviews) <= set(rows):
        raise ValueError("Reviews must be an object keyed by existing question IDs.")
    for key, review in reviews.items():
        for field in ("correct", "citations_supported", "behavior_satisfied", "critical_error"):
            if not isinstance(review.get(field), bool):
                raise ValueError("Review requires boolean " + field)
        if not isinstance(review.get("notes"), str):
            raise ValueError("Review requires notes.")
        rows[key].setdefault("reviews", {})[reviewer] = review
    save_report(run_path, report)
    return summarize(report, reviewer)


def export_public(client, run_path):
    report = read_json(run_path)
    manifest_path = ROOT / "examples/northstar/manifest.json"
    suite_path = ROOT / "evaluation/northstar.jsonl"
    if (report.get("classification") != "public-demo" or report.get("corpus_id") != "northstar-demo"
            or report.get("manifest_sha256") != sha256(manifest_path) or report.get("suite_sha256") != sha256(suite_path)):
        raise ValueError("Only unchanged bundled fictional-corpus evaluations can be exported.")
    data = manifest(manifest_path)
    if report["document_hashes"] != {doc["id"]: doc["sha256"] for doc in data["documents"]}:
        raise ValueError("Report document hashes do not match the fictional corpus.")
    state = read_json(home() / "ingestion.json", {}).get(data["id"], {})
    verify_corpus(client, data, state)
    known = {doc["id"] for doc in data["documents"]}
    if any(not set(row["retrieved_source_ids"]) <= known for row in report["results"]):
        raise ValueError("Unknown source in report; export refused.")
    destination = ROOT / "reports/public" / report["id"]
    destination.mkdir(parents=True, exist_ok=True)
    save_report(destination / "evaluation.json", report)
    print(str(destination))
    return destination
