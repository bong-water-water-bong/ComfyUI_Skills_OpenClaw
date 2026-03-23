from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import comfyui_client


class ExecuteWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.workflow_path = base / "workflow.json"
        self.schema_path = base / "schema.json"

        self.workflow_path.write_text(
            json.dumps({"1": {"inputs": {"text": "placeholder"}}}),
            encoding="utf-8",
        )
        self.schema_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "parameters": {
                        "prompt": {
                            "node_id": "1",
                            "field": "text",
                            "type": "string",
                            "required": True,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_queue_disappearance_returns_error_payload_and_finalizes_history(self) -> None:
        record = {"run_id": "run-123"}

        with (
            patch.object(comfyui_client.uuid, "uuid4", return_value="run-123"),
            patch.object(
                comfyui_client,
                "get_server_by_id",
                return_value={
                    "id": "local",
                    "enabled": True,
                    "url": "http://127.0.0.1:8188",
                    "output_dir": self.temp_dir.name,
                },
            ),
            patch.object(comfyui_client, "get_server_workflow_path", return_value=self.workflow_path),
            patch.object(comfyui_client, "get_server_schema_path", return_value=self.schema_path),
            patch.object(comfyui_client, "build_run_record", return_value=record),
            patch.object(comfyui_client, "save_run_record"),
            patch.object(comfyui_client, "queue_prompt", return_value={"prompt_id": "prompt-123"}),
            patch.object(comfyui_client, "get_history", return_value=None),
            patch.object(comfyui_client, "is_job_in_queue", return_value=False),
            patch.object(comfyui_client, "_mark_record_running"),
            patch.object(comfyui_client, "_finalize_record") as finalize_record,
        ):
            result = comfyui_client.execute_workflow_by_ids("local", "demo", {"prompt": "hello world"})

        self.assertEqual(
            result,
            {
                "status": "error",
                "error": "Job prompt-123 disappeared from queue without producing results",
                "run_id": "run-123",
            },
        )
        finalize_record.assert_called_once_with(
            record,
            "local",
            "demo",
            status="error",
            resolved_args={"prompt": "hello world"},
            prompt_id="prompt-123",
            error_message="Job prompt-123 disappeared from queue without producing results",
        )


if __name__ == "__main__":
    unittest.main()
