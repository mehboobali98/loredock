import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from loredock.api import APIError, Client
from loredock.config import ROOT, home, initialize
from loredock.evaluate import load_suite, summarize
from loredock.ingest import ingest, manifest, verify_corpus
from loredock.runtime import safe_extract


class Boundaries(unittest.TestCase):
    def test_private_data_cannot_be_inside_checkout(self):
        with patch.dict(os.environ, {"LOREDOCK_HOME": str(ROOT / "data")}):
            with self.assertRaises(ValueError):
                home()

    def test_initialize_preserves_private_environment_and_restricts_key_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"LOREDOCK_HOME": directory}):
            initialize()
            environment = Path(directory, "server.env")
            environment.write_text("FIXTURE_SETTING=retained\n")
            initialize()
            self.assertEqual(environment.read_text(), "FIXTURE_SETTING=retained\n")
            self.assertEqual(Path(directory, "config.json").stat().st_mode & 0o777, 0o600)

    def test_metadata_change_invalidates_ingestion_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.md").write_text("Fictional policy text, unchanged.")
            data = {"id": "private-fixture", "classification": "private", "workspaces": {"policies": "Fixture"},
                    "documents": [{"id": "LD-FIXTURE", "file": "source.md", "workspace": "policies", "title": "Fixture",
                                   "owner": "Example", "date": "2026-01-01", "authority": "Draft", "source_url": "https://example.invalid"}]}
            path = root / "manifest.json"
            path.write_text(json.dumps(data))
            first = manifest(path)["documents"][0]["sha256"]
            data["documents"][0]["authority"] = "Approved policy"
            path.write_text(json.dumps(data))
            self.assertNotEqual(first, manifest(path)["documents"][0]["sha256"])

    def test_remote_or_credentialed_endpoints_rejected(self):
        for url in ("https://cloud.example", "http://127.0.0.1.evil.test", "http://secret@localhost:3001", "http://localhost:3001/path"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Client(url, "secret")

    def test_missing_key_fails_before_network(self):
        with self.assertRaises(APIError):
            Client("http://127.0.0.1:3001").get("/system")

    def test_suite_distribution_and_sources(self):
        rows = load_suite(ROOT / "evaluation/northstar.jsonl")
        self.assertEqual({kind: sum(row["kind"] == kind for row in rows) for kind in ("answerable", "unsupported", "ambiguous")},
                         {"answerable": 20, "unsupported": 5, "ambiguous": 5})
        docs = manifest(ROOT / "examples/northstar/manifest.json")
        known = {doc["id"] for doc in docs["documents"]}
        for row in rows:
            self.assertTrue(set(row["expected_sources"]) <= known)

    def test_unreviewed_results_cannot_pass_quality_gate(self):
        rows = [{**row, "reviews": {}, "latency_seconds": 1, "error": None} for row in load_suite(ROOT / "evaluation/northstar.jsonl")]
        report = {"results": rows}
        self.assertEqual(summarize(report)["quality_gate"], "pending")
        for row in rows:
            row["reviews"]["agent"] = {"correct": True, "behavior_satisfied": True, "citations_supported": True, "critical_error": False}
        self.assertEqual(summarize(report, "agent")["quality_gate"], "pass")
        self.assertEqual(summarize(report)["quality_gate"], "pending")

    def test_one_critical_error_blocks_acceptance(self):
        rows = [{**row, "reviews": {"human": {"correct": True, "behavior_satisfied": True, "citations_supported": True,
                          "critical_error": False}}, "latency_seconds": 1, "error": None}
                for row in load_suite(ROOT / "evaluation/northstar.jsonl")]
        rows[0]["reviews"]["human"]["critical_error"] = True
        self.assertEqual(summarize({"results": rows})["quality_gate"], "fail")

    def test_latency_counts_errors_in_original_ten_not_replacement_questions(self):
        rows = [{**row, "reviews": {}, "latency_seconds": 1, "error": "APIError" if i < 3 else None}
                for i, row in enumerate(load_suite(ROOT / "evaluation/northstar.jsonl"))]
        result = summarize({"results": rows, "warmup_completed": True})
        self.assertEqual(result["standard_warm_questions"], 10)
        self.assertEqual(result["within_30_seconds"], 7)
        self.assertEqual(result["latency_gate"], "fail")

    def test_http_200_with_failed_embedding_retains_old_version(self):
        class Fake:
            def __init__(self):
                self.deletes = []
            def post(self, endpoint, body):
                if endpoint.endswith("/new"):
                    return {"workspace": {"slug": "demo"}}
                if endpoint == "/document/raw-text":
                    return {"success": True, "documents": [{"location": "new.json"}]}
                if endpoint.endswith("/update-embeddings"):
                    self.deletes.extend(body["deletes"])
                return {}
            def workspace(self, _):
                return {"documents": [{"docpath": "old.json"}]}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"LOREDOCK_HOME": directory}):
            state = {"northstar-demo": {"workspaces": {"policies": "demo", "context": "context"},
                     "documents": {"LD-LEAVE": {"sha256": "old-hash", "locations": ["old.json"], "workspace": "demo"}}}}
            Path(directory, "ingestion.json").write_text(json.dumps(state))
            fake = Fake()
            with self.assertRaises(APIError):
                ingest(fake, ROOT / "examples/northstar/manifest.json")
            self.assertEqual(fake.deletes, [])
            saved = json.loads(Path(directory, "ingestion.json").read_text())
            self.assertEqual(saved["northstar-demo"]["documents"]["LD-LEAVE"]["locations"], ["old.json"])

    def test_application_error_in_http_success_is_not_accepted(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"success": false, "error": "private text"}'
        class Opener:
            def open(self, *args, **kwargs): return Response()
        api = Client("http://127.0.0.1:3001", "secret")
        api.opener = Opener()
        with self.assertRaises(APIError) as raised:
            api.post("/document/raw-text", {})
        self.assertNotIn("private text", str(raised.exception))

    def test_unregistered_workspace_document_aborts_evaluation(self):
        data = {"documents": [{"id": "LD-X", "sha256": "hash"}]}
        state = {"workspaces": {"policies": "demo"}, "documents": {"LD-X": {"sha256": "hash", "locations": ["known"], "workspace": "demo"}}}
        class Fake:
            def workspace(self, _):
                return {"documents": [{"docpath": "known"}, {"docpath": "private-extra"}]}
        with self.assertRaises(ValueError):
            verify_corpus(Fake(), data, state)

    def test_backup_rejects_traversal_links_and_special_files(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("storage/link", tarfile.SYMTYPE), ("storage/device", tarfile.CHRTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w") as archive:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "/tmp/escape"
                    archive.addfile(member)
                buffer.seek(0)
                with tarfile.open(fileobj=buffer) as archive, self.assertRaises(ValueError):
                    safe_extract(archive, Path(directory))

    def test_backup_extracts_allowed_regular_files(self):
        with tempfile.TemporaryDirectory() as directory:
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                member = tarfile.TarInfo("storage/test.txt")
                member.size = 4
                archive.addfile(member, io.BytesIO(b"demo"))
            buffer.seek(0)
            with tarfile.open(fileobj=buffer) as archive:
                safe_extract(archive, directory)
            self.assertEqual((Path(directory) / "storage/test.txt").read_text(), "demo")


if __name__ == "__main__":
    unittest.main()
