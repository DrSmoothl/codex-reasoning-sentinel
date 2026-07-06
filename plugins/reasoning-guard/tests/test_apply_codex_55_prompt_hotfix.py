from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_codex_55_prompt_hotfix.py"


def load_hotfix_module():
    spec = importlib.util.spec_from_file_location("apply_codex_55_prompt_hotfix", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ApplyCodex55PromptHotfixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hotfix = load_hotfix_module()

    def write_models_cache(self, codex_home: Path, base_instructions: str) -> None:
        payload = {
            "models": [
                {
                    "slug": "gpt-5.5",
                    "base_instructions": base_instructions,
                }
            ]
        }
        (codex_home / "models_cache.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_strip_intermediary_updates_removes_final_block(self) -> None:
        stripped, removed = self.hotfix.strip_intermediary_updates(
            "alpha\n## Final answer instructions\nbeta\n\n## Intermediary updates\nbad\n"
        )
        self.assertTrue(removed)
        self.assertEqual(stripped, "alpha\n## Final answer instructions\nbeta\n")

    def test_apply_hotfix_updates_prompt_and_top_level_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            self.write_models_cache(codex_home, "alpha\n\n## Intermediary updates\nbad\n")
            (codex_home / "config.toml").write_text(
                'model = "gpt-5.4"\n\n[features]\nmemories = true\n',
                encoding="utf-8",
            )

            result = self.hotfix.apply_hotfix(codex_home)

            self.assertTrue(result["source_had_intermediary_updates"])
            self.assertTrue(result["instructions_change"])
            self.assertTrue(result["config_change"])
            self.assertEqual((codex_home / "model-instructions.md").read_text(encoding="utf-8"), "alpha\n")
            self.assertEqual(
                (codex_home / "config.toml").read_text(encoding="utf-8"),
                'model = "gpt-5.5"\nmodel_instructions_file = "~/.codex/model-instructions.md"\n\n[features]\nmemories = true\n',
            )

            check = self.hotfix.apply_hotfix(codex_home, check=True)
            self.assertFalse(check["instructions_change"])
            self.assertFalse(check["config_change"])

    def test_update_top_level_config_preserves_crlf(self) -> None:
        updated = self.hotfix.update_top_level_config(
            'model = "gpt-5.5"\r\nmodel_instructions_file = "~/.codex/model-instructions.md"\r\n\r\n[features]\r\nmemories = true\r\n',
            {
                "model": "gpt-5.5",
                "model_instructions_file": "~/.codex/model-instructions.md",
            },
        )
        self.assertIn("\r\n[features]\r\n", updated)
        self.assertNotIn("\n[features]\n", updated)


if __name__ == "__main__":
    unittest.main()
