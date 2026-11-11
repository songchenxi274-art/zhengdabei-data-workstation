from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.csv_export import UnsafeCsvValueError, dataframe_to_safe_csv


class SafeCsvTests(unittest.TestCase):
    def test_formula_prefixes_after_whitespace_and_controls_are_neutralized(self):
        frame = pd.DataFrame(
            {
                "plain": [
                    "=1+1",
                    "  +SUM(A1:A2)",
                    "\t@cmd",
                    "\r-1+2",
                    "\x01=2+2",
                ]
            }
        )
        output = dataframe_to_safe_csv(frame)
        self.assertIn("'=1+1", output)
        self.assertIn("'  +SUM(A1:A2)", output)
        self.assertIn("'\t@cmd", output)
        self.assertIn("'\r-1+2", output)
        self.assertIn("'\x01=2+2", output)

    def test_numeric_negative_is_preserved(self):
        frame = pd.DataFrame({"value": [-1.5, 2.0]})
        output = dataframe_to_safe_csv(frame)
        self.assertIn("-1.5", output)
        self.assertNotIn("'-1.5", output)

    def test_header_formula_is_neutralized(self):
        frame = pd.DataFrame([["safe"]], columns=["=danger"])
        output = dataframe_to_safe_csv(frame)
        self.assertTrue(output.startswith("'=danger\n"))

    def test_disallowed_control_character_is_rejected(self):
        frame = pd.DataFrame({"value": ["abc\x00def"]})
        with self.assertRaises(UnsafeCsvValueError):
            dataframe_to_safe_csv(frame)

    def test_bom_and_zero_width_format_characters_do_not_bypass_formula_guard(self):
        frame = pd.DataFrame(
            {
                "value": [
                    "\ufeff=1+1",
                    "\u200b=1+1",
                    "\u200e@SUM(A1:A2)",
                ]
            }
        )
        output = dataframe_to_safe_csv(frame)
        self.assertIn("'\ufeff=1+1", output)
        self.assertIn("'\u200b=1+1", output)
        self.assertIn("'\u200e@SUM(A1:A2)", output)


if __name__ == "__main__":
    unittest.main()
