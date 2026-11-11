from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    specification = importlib.util.spec_from_file_location(
        name,
        ROOT / relative_path,
    )
    module = importlib.util.module_from_spec(specification)
    assert specification.loader is not None
    specification.loader.exec_module(module)
    return module


class SpssValidationTests(unittest.TestCase):
    def test_synthetic_fixtures_and_candidate_values_are_reproducible(self):
        prepare = load_script("prepare_spss_validation", "scripts/prepare_spss_validation.py")
        evaluate = load_script("evaluate_spss_validation", "scripts/evaluate_spss_validation.py")
        prepare.main()
        evaluate.main()
        result = json.loads(
            (ROOT / "work" / "spss_validation" / "app_expected.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result["pearson"]["n"], 18)
        self.assertAlmostEqual(result["pearson"]["coefficient"], 0.9476308426653285)
        self.assertEqual(result["reliability_3"]["n_complete"], 28)
        self.assertAlmostEqual(result["reliability_2"]["alpha"], 1.0)


if __name__ == "__main__":
    unittest.main()
