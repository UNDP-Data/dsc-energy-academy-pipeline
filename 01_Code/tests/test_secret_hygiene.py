from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_repository_hygiene import check_path
from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.env import EnvConfig
from sea_pipeline.shared.redaction import SecretRedactor, redact_text
from sea_pipeline.shared.logging import format_stage_result
from sea_pipeline.shared.notebook_runtime import _collect_output_text, _streaming_client_class
from sea_pipeline.shared.notebook_runtime import execute_notebook_stage, NotebookStage
from sea_pipeline.shared.paths import RepoPaths
from sea_pipeline.auxiliary.avatars.heygen import run_avatar_script_command
from sea_pipeline.photo.resumable import PhotoExportJournal
import nbformat


class SecretHygieneTests(unittest.TestCase):
    def test_validation_never_returns_credentials(self):
        with patch.dict(os.environ, {"FIGMA_TOKEN": "test-private-value", "SAS_URL": "test-signed-url"}, clear=True):
            result = EnvConfig().validate_keys(["figma_token", "sas_url", "heygen_api_key"])
            self.assertFalse(result["ok"])
            self.assertEqual(result["missing"], ["HEYGEN_API_KEY"])
            self.assertEqual(result["values"]["FIGMA_TOKEN"], "[REDACTED]")
            self.assertNotIn("test-private-value", json.dumps(result))
            self.assertNotIn("test-signed-url", json.dumps(result))

    def test_secret_fields_are_not_in_config_repr(self):
        env = EnvConfig(figma_token="test-private-value", azure_openai_api_key="test-private-value",
                        sas_url="test-private-value", heygen_api_key="test-private-value")
        self.assertNotIn("test-private-value", repr(env))

    def test_dotenv_is_resolved_against_selected_repo_not_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01_Code").mkdir()
            (root / "01_Code" / ".env").write_text("FIGMA_TOKEN=test-file-value\n")
            with patch.dict(os.environ, {}, clear=True):
                config = PipelineConfig.from_repo_root(root)
                self.assertEqual(config.env.figma_token, "test-file-value")
            with patch.dict(os.environ, {"FIGMA_TOKEN": "test-process-value"}, clear=True):
                self.assertEqual(PipelineConfig.from_repo_root(root).env.figma_token, "test-process-value")
            with patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(PipelineConfig.from_repo_root(root, load_dotenv_file=False).env.figma_token)

    def test_private_files_and_generated_artifacts_are_rejected(self):
        for name in ["nested/.env", ".env.production", "file.key", "a/__pycache__/file.pyc",
                     "a/.ipynb_checkpoints/test.ipynb", ".aws/credentials"]:
            with self.subTest(name=name):
                self.assertTrue(check_path(name))
        self.assertEqual(check_path("01_Code/.env.example"), [])

    def test_saved_outputs_in_both_notebook_representations_are_rejected(self):
        data = {"cells": [{"cell_type": "code", "execution_count": 1,
                           "outputs": [{"text": "test-private-value"}]}]}
        for path in ["test.ipynb", "sea_pipeline/_legacy_notebooks/test.json"]:
            errors = check_path(path, json.dumps(data).encode())
            self.assertTrue(errors)
            self.assertNotIn("test-private-value", str(errors))
            self.assertEqual(check_path(path, b'{"cells": [{"outputs": [], "execution_count": null}]}'), [])

    def test_signed_urls_and_encoded_credentials_are_redacted(self):
        secret = "test/private+credential="
        with patch.dict(os.environ, {"FIGMA_TOKEN": secret}, clear=True):
            text = redact_text("Progress 2/3 " + secret + " test%2Fprivate%2Bcredential%3D "
                               "https://example.test/a?sig=fake&x=1")
            self.assertNotIn(secret, text)
            self.assertNotIn("sig=fake", text)
            self.assertNotIn("%2Fprivate", text)
            self.assertIn("Progress 2/3", text)
            self.assertIn("&x=1", text)

    def test_split_stream_messages_do_not_leak_and_flush_preserves_progress(self):
        redactor = SecretRedactor(["synthetic-secret"])
        self.assertEqual(redactor.stream("stdout", "Starting synthetic-"), "")
        self.assertEqual(redactor.stream("stdout", "secret\nDone"), "Starting [REDACTED]\n")
        self.assertEqual(redactor.stream("stdout", "", final=True), "Done")

    def test_collected_results_and_summary_are_redacted(self):
        with patch.dict(os.environ, {"FIGMA_TOKEN": "synthetic-secret"}, clear=True):
            notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("pass")])
            notebook.cells[0].outputs = [nbformat.v4.new_output("stream", name="stdout", text="synthetic-"),
                                         nbformat.v4.new_output("stream", name="stdout", text="secret")]
            self.assertEqual(_collect_output_text(notebook)[0], "[REDACTED]")
            result = {"stage": "test", "summary": {"nested": "synthetic-secret"}}
            self.assertNotIn("synthetic-secret", format_stage_result(result))
            self.assertEqual(result["summary"]["nested"], "synthetic-secret")

    def test_live_stream_client_redacts_without_losing_logs(self):
        class Client:
            def process_message(self, msg, cell, index):
                pass
        client = _streaming_client_class(Client, SecretRedactor(["synthetic-secret"]))()
        output = io.StringIO()
        with redirect_stdout(output):
            for chunk in ("Loaded\nsynthetic-", "secret\nFinished"):
                client.process_message({"msg_type": "stream", "content": {"name": "stdout", "text": chunk}}, None, 0)
            client.flush_safe_output()
        self.assertEqual(output.getvalue(), "Loaded\n[REDACTED]\nFinished")

    def test_execution_error_is_sanitized_without_hiding_failure(self):
        class FailingClient:
            def __init__(self, *args, **kwargs):
                pass
            def execute(self):
                raise ValueError("Could not authenticate synthetic-private-value")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01_Code").mkdir()
            nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("pass")]),
                           root / "01_Code" / "test.ipynb")
            config = PipelineConfig(root, RepoPaths.from_root(root), EnvConfig(figma_token="synthetic-private-value"))
            with patch("sea_pipeline.shared.notebook_runtime.NotebookClient", FailingClient):
                with self.assertRaises(RuntimeError) as caught:
                    execute_notebook_stage(config, NotebookStage("test", "test.ipynb", (0,), "test"))
            self.assertIn("Could not authenticate [REDACTED]", str(caught.exception))
            self.assertNotIn("synthetic-private-value", str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    def test_avatar_subprocess_result_is_safe_to_display_directly(self):
        config = PipelineConfig.from_repo_root(load_dotenv_file=False)
        config.env = EnvConfig(heygen_api_key="synthetic-private-value")
        completed = SimpleNamespace(returncode=1, stdout="Progress synthetic-private-value", stderr="synthetic-private-value failed")
        with patch("sea_pipeline.auxiliary.avatars.heygen.subprocess.run", return_value=completed):
            result = run_avatar_script_command(config, "generate_payloads")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["returncode"], 1)
        self.assertNotIn("synthetic-private-value", str(result))
        self.assertIn("Progress", result["stdout"])

    def test_python_repr_escaping_does_not_expose_password(self):
        secret = "synthetic'password\"value"
        with patch.dict(os.environ, {"PIWIGO_PASSWORD": secret}, clear=True):
            result = format_stage_result({"summary": {"password": secret}})
            self.assertNotIn(repr(secret)[1:-1], result)
            self.assertIn("[REDACTED]", result)

    def test_photo_journal_persists_safe_details_without_breaking_resume(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"FIGMA_TOKEN": "synthetic-private-value"}, clear=True):
            journal = PhotoExportJournal.load(tmp, "test")
            journal.record_miss(blob_name="miss.webp", node_id="1:1", file_id="file", page_name="Page",
                                reason="network", detail="synthetic-private-value failed",
                                url="https://example.test/a?X-Amz-Signature=fake")
            journal.record_success(blob_name="ok.webp", node_id="1:2", file_id="file", page_name="Page",
                                   url="https://example.test/b?sig=fake")
            journal.flush_snapshots(force=True)
            for path in Path(tmp).iterdir():
                text = path.read_text()
                self.assertNotIn("synthetic-private-value", text)
                self.assertNotIn("=fake", text)
            loaded = PhotoExportJournal.load(tmp, "test")
            self.assertTrue(loaded.is_missed("miss.webp"))
            self.assertTrue(loaded.is_successful("ok.webp"))


if __name__ == "__main__":
    unittest.main()
