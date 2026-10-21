import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loredock.api import APIError, Client
from loredock.config import ROOT, home, initialize, read_json
from loredock.evaluate import (
    citation_ids,
    citation_links,
    load_suite,
    review_passes,
    source_ids,
    summarize,
)
from loredock.ingest import INGESTION_REVISION, ingest, manifest, upload, verify_corpus
from loredock.runtime import _replace_state, safe_extract


class Boundaries(unittest.TestCase):
    def test_reasoning_mentions_do_not_count_as_final_answer_citations(self):
        raw = "<think>Consider [LD-LEAVE]</think>The policy states it [LD-LOCATION]."
        self.assertEqual(citation_ids(raw), ["LD-LOCATION"])
        linked = "<think>[Wrong](https://example.invalid/wrong)</think>Rule [Policy](https://example.invalid/policy)."
        self.assertEqual(citation_links(linked), ["https://example.invalid/policy"])

    def test_upload_uses_epoch_milliseconds_and_supported_link_provenance(self):
        class Fake:
            def post(self, endpoint, body):
                self.metadata = body["metadata"]
                return {"documents": [{"location": "fixture.json"}]}

        doc = manifest(ROOT / "examples/northstar/manifest.json")["documents"][0]
        fake = Fake()
        upload(fake, doc)
        self.assertEqual(fake.metadata["published"], 1767225600000)
        self.assertEqual(fake.metadata["chunkSource"], "link://" + doc["source_url"])

    def test_wrong_citation_blocks_an_ambiguous_answer_pass(self):
        row = {"kind": "ambiguous", "error": None}
        review = {
            "correct": True,
            "behavior_satisfied": True,
            "citations_supported": False,
        }
        self.assertFalse(review_passes(row, review))

    def test_missing_required_json_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                read_json(path)
            self.assertEqual(read_json(path, {}), {})

    def test_partial_restore_failure_rolls_back_installed_files(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"LOREDOCK_HOME": directory}),
        ):
            root = Path(directory)
            staged, recovery = root / "staged", root / "recovery"
            staged.mkdir()
            recovery.mkdir()
            for name in ("storage", "server.env", "config.json"):
                (root / name).write_text("old")
                (staged / name).write_text("new")
            rename = Path.rename

            def fail_during_swap(source, destination):
                if source == staged / "config.json":
                    raise OSError(
                        "Simulated failure after earlier entries were replaced"
                    )
                return rename(source, destination)

            with (
                patch.object(Path, "rename", fail_during_swap),
                self.assertRaises(OSError),
            ):
                _replace_state(staged, recovery)
            for name in ("storage", "server.env", "config.json"):
                self.assertEqual((root / name).read_text(), "old")
                self.assertEqual((staged / name).read_text(), "new")
            self.assertFalse(list(recovery.iterdir()))

    def test_private_data_cannot_be_inside_checkout(self):
        with patch.dict(os.environ, {"LOREDOCK_HOME": str(ROOT / "data")}):
            with self.assertRaises(ValueError):
                home()

    def test_initialize_preserves_private_environment_and_restricts_key_file(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"LOREDOCK_HOME": directory}),
        ):
            initialize()
            environment = Path(directory, "server.env")
            environment.write_text("FIXTURE_SETTING=retained\n")
            initialize()
            self.assertEqual(environment.read_text(), "FIXTURE_SETTING=retained\n")
            self.assertEqual(
                Path(directory, "config.json").stat().st_mode & 0o777, 0o600
            )

    def test_metadata_change_invalidates_ingestion_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.md").write_text("Fictional policy text, unchanged.")
            data = {
                "id": "private-fixture",
                "classification": "private",
                "workspaces": {"policies": "Fixture"},
                "documents": [
                    {
                        "id": "LD-FIXTURE",
                        "file": "source.md",
                        "workspace": "policies",
                        "title": "Fixture",
                        "owner": "Example",
                        "date": "2026-01-01",
                        "authority": "Draft",
                        "source_url": "https://example.invalid",
                    }
                ],
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(data))
            first = manifest(path)["documents"][0]["sha256"]
            data["documents"][0]["authority"] = "Approved policy"
            path.write_text(json.dumps(data))
            self.assertNotEqual(first, manifest(path)["documents"][0]["sha256"])

    def test_normalized_source_titles_map_without_counting_passage_mentions(self):
        sources = [
            {"title": "ld-leave-leave-policy.txt", "text": "Related: LD-LOCATION"}
        ]
        self.assertEqual(source_ids(sources, {"LD-LEAVE", "LD-LOCATION"}), ["LD-LEAVE"])

    def test_format_upgrade_reuses_completed_embedding_after_lost_response(self):
        class Fake:
            def __init__(self):
                self.paths = {"old.json"}
                self.uploads = 0
                self.failed = False

            def post(self, endpoint, body):
                if endpoint == "/document/raw-text":
                    self.uploads += 1
                    return {"documents": [{"location": "new.json"}]}
                if endpoint.endswith("/update-embeddings"):
                    self.paths.update(body["adds"])
                    self.paths.difference_update(body["deletes"])
                    if body["adds"] and not self.failed:
                        self.failed = True
                        raise APIError(
                            "Simulated response lost after embedding completed"
                        )
                return {}

            def workspace(self, _):
                return {"documents": [{"docpath": path} for path in sorted(self.paths)]}

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"LOREDOCK_HOME": directory}),
        ):
            root = Path(directory)
            (root / "source.md").write_text("A fictional replacement policy.")
            data = {
                "id": "recovery",
                "classification": "private",
                "workspaces": {"policies": "Fixture"},
                "documents": [
                    {
                        "id": "LD-FIXTURE",
                        "file": "source.md",
                        "workspace": "policies",
                        "title": "Fixture",
                        "owner": "Example",
                        "date": "2026-01-01",
                        "authority": "Approved",
                        "source_url": "https://example.invalid",
                    }
                ],
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(data))
            state = {
                "recovery": {
                    "workspaces": {"policies": "fixture"},
                    "documents": {
                        "LD-FIXTURE": {
                            "sha256": manifest(path)["documents"][0]["sha256"],
                            "locations": ["old.json"],
                            "workspace": "fixture",
                        }
                    },
                }
            }
            (root / "ingestion.json").write_text(json.dumps(state))
            fake = Fake()
            with self.assertRaises(APIError):
                ingest(fake, path)
            ingest(fake, path)
            self.assertEqual(fake.uploads, 1)
            self.assertEqual(fake.paths, {"new.json"})
            self.assertEqual(
                json.loads((root / "ingestion.json").read_text())["recovery"][
                    "pending"
                ],
                {},
            )

    def test_remote_or_credentialed_endpoints_rejected(self):
        for url in (
            "https://cloud.example",
            "http://127.0.0.1.evil.test",
            "http://secret@localhost:3001",
            "http://localhost:3001/path",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Client(url, "secret")

    def test_missing_key_fails_before_network(self):
        with self.assertRaises(APIError):
            Client("http://127.0.0.1:3001").get("/system")

    def test_suite_distribution_and_sources(self):
        rows = load_suite(ROOT / "evaluation/northstar.jsonl")
        self.assertEqual(
            {
                kind: sum(row["kind"] == kind for row in rows)
                for kind in ("answerable", "unsupported", "ambiguous")
            },
            {"answerable": 20, "unsupported": 5, "ambiguous": 5},
        )
        docs = manifest(ROOT / "examples/northstar/manifest.json")
        known = {doc["id"] for doc in docs["documents"]}
        for row in rows:
            self.assertTrue(set(row["expected_sources"]) <= known)

    def test_unreviewed_results_cannot_pass_quality_gate(self):
        rows = [
            {**row, "reviews": {}, "latency_seconds": 1, "error": None}
            for row in load_suite(ROOT / "evaluation/northstar.jsonl")
        ]
        report = {"results": rows}
        self.assertEqual(summarize(report)["quality_gate"], "pending")
        for row in rows:
            row["reviews"]["agent"] = {
                "correct": True,
                "behavior_satisfied": True,
                "citations_supported": True,
                "critical_error": False,
            }
        self.assertEqual(summarize(report, "agent")["quality_gate"], "pass")
        self.assertEqual(summarize(report)["quality_gate"], "pending")

    def test_one_critical_error_blocks_acceptance(self):
        rows = [
            {
                **row,
                "reviews": {
                    "human": {
                        "correct": True,
                        "behavior_satisfied": True,
                        "citations_supported": True,
                        "critical_error": False,
                    }
                },
                "latency_seconds": 1,
                "error": None,
            }
            for row in load_suite(ROOT / "evaluation/northstar.jsonl")
        ]
        rows[0]["reviews"]["human"]["critical_error"] = True
        self.assertEqual(summarize({"results": rows})["quality_gate"], "fail")

    def test_latency_counts_errors_in_original_ten_not_replacement_questions(self):
        rows = [
            {
                **row,
                "reviews": {},
                "latency_seconds": 1,
                "error": "APIError" if i < 3 else None,
            }
            for i, row in enumerate(load_suite(ROOT / "evaluation/northstar.jsonl"))
        ]
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

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"LOREDOCK_HOME": directory}),
        ):
            state = {
                "northstar-demo": {
                    "workspaces": {"policies": "demo", "context": "context"},
                    "documents": {
                        "LD-LEAVE": {
                            "sha256": "old-hash",
                            "locations": ["old.json"],
                            "workspace": "demo",
                        }
                    },
                }
            }
            Path(directory, "ingestion.json").write_text(json.dumps(state))
            fake = Fake()
            with self.assertRaises(APIError):
                ingest(fake, ROOT / "examples/northstar/manifest.json")
            self.assertEqual(fake.deletes, [])
            saved = json.loads(Path(directory, "ingestion.json").read_text())
            self.assertEqual(
                saved["northstar-demo"]["documents"]["LD-LEAVE"]["locations"],
                ["old.json"],
            )

    def test_application_error_in_http_success_is_not_accepted(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return b'{"success": false, "error": "private text"}'

        class Opener:
            def open(self, *args, **kwargs):
                return Response()

        api = Client("http://127.0.0.1:3001", "secret")
        api.opener = Opener()
        with self.assertRaises(APIError) as raised:
            api.post("/document/raw-text", {})
        self.assertNotIn("private text", str(raised.exception))

    def test_unregistered_workspace_document_aborts_evaluation(self):
        data = {"documents": [{"id": "LD-X", "sha256": "hash"}]}
        state = {
            "workspaces": {"policies": "demo"},
            "documents": {
                "LD-X": {
                    "sha256": "hash",
                    "locations": ["known"],
                    "workspace": "demo",
                    "format_revision": INGESTION_REVISION,
                }
            },
        }

        class Fake:
            def workspace(self, _):
                return {
                    "documents": [{"docpath": "known"}, {"docpath": "private-extra"}]
                }

        with self.assertRaisesRegex(ValueError, "unregistered"):
            verify_corpus(Fake(), data, state)

    def test_backup_rejects_traversal_links_and_special_files(self):
        for name, kind in (
            ("../escape", tarfile.REGTYPE),
            ("storage/link", tarfile.SYMTYPE),
            ("storage/device", tarfile.CHRTYPE),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w") as archive:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "/tmp/escape"
                    archive.addfile(member)
                buffer.seek(0)
                with (
                    tarfile.open(fileobj=buffer) as archive,
                    self.assertRaises(ValueError),
                ):
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
