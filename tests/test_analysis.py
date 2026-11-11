from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.analysis import (
    calculate_correlation,
    calculate_reliability,
    create_static_scatter_svg,
    ordinal_descriptives,
    numeric_descriptives,
)
from research_desk.models import SamplingDesign


class AnalysisTests(unittest.TestCase):
    def test_numeric_descriptives_use_sample_standard_deviation(self):
        frame = pd.DataFrame({"score": [1, 2, 3, None]})
        result = numeric_descriptives(frame, ["score"]).iloc[0]
        self.assertEqual(result["有效数"], 3)
        self.assertEqual(result["缺失数"], 1)
        self.assertAlmostEqual(result["标准差"], 1.0)

    def test_correlation_suppresses_p_value_below_ui_threshold(self):
        frame = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})
        result = calculate_correlation(
            frame,
            "x",
            "y",
            "pearson",
            SamplingDesign.ORDINARY,
        )
        self.assertAlmostEqual(result.coefficient, 1.0)
        self.assertIsNone(result.p_value)
        self.assertIn("少于 10", result.p_value_reason or "")

    def test_complex_sampling_disables_inference(self):
        frame = pd.DataFrame(
            {"x": range(12), "y": [value * 2 + (index % 2) for index, value in enumerate(range(12))]}
        )
        result = calculate_correlation(
            frame,
            "x",
            "y",
            "spearman",
            SamplingDesign.COMPLEX,
        )
        self.assertIsNone(result.p_value)
        self.assertIn("抽样声明", result.p_value_reason or "")

    def test_constant_field_correlation_is_rejected(self):
        frame = pd.DataFrame({"x": [1, 1, 1], "y": [1, 2, 3]})
        with self.assertRaises(ValueError):
            calculate_correlation(
                frame,
                "x",
                "y",
                "pearson",
                SamplingDesign.ORDINARY,
            )

    def test_two_item_reliability_computes_without_deleted_alpha(self):
        frame = pd.DataFrame(
            {
                "q1": [1, 2, 3, 4, 5, 5],
                "q2": [1, 2, 3, 4, 5, 5],
            }
        )
        result = calculate_reliability(
            frame,
            ["q1", "q2"],
            [],
            1,
            5,
            SamplingDesign.ORDINARY,
        )
        self.assertEqual(result.n_complete, 6)
        self.assertAlmostEqual(result.alpha, 1.0)
        self.assertTrue(result.item_statistics.empty)

    def test_reliability_reverse_scoring(self):
        frame = pd.DataFrame(
            {
                "q1": [1, 2, 3, 4, 5, 5],
                "q2": [5, 4, 3, 2, 1, 1],
                "q3": [1, 2, 3, 4, 5, 5],
            }
        )
        result = calculate_reliability(
            frame,
            ["q1", "q2", "q3"],
            ["q2"],
            1,
            5,
            SamplingDesign.ORDINARY,
        )
        self.assertEqual(result.n_complete, 6)
        self.assertEqual(result.item_count, 3)
        self.assertGreater(result.alpha, 0.9)

    def test_static_scatter_contains_all_points(self):
        frame = pd.DataFrame({"x": [1, 2, 3], "y": [3, 2, 1]})
        svg = create_static_scatter_svg(frame, "x", "y")
        self.assertIn("<svg", svg)
        self.assertEqual(svg.count("<circle"), 3)

    def test_static_scatter_escapes_field_names(self):
        frame = pd.DataFrame({"x": [1, 2], "<script>": [2, 1]})
        svg = create_static_scatter_svg(frame, "x", "<script>")
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;", svg)

    def test_infinite_numeric_value_is_removed_before_correlation(self):
        frame = pd.DataFrame(
            {
                "x": [1.0, np.inf, 2.0, 3.0, 4.0],
                "y": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        result = calculate_correlation(
            frame,
            "x",
            "y",
            "pearson",
            SamplingDesign.ORDINARY,
        )
        self.assertEqual(result.n, 4)
        self.assertTrue(np.isfinite(result.coefficient))

    def test_reliability_marks_undefined_item_statistics(self):
        frame = pd.DataFrame(
            {
                "a": [1, 2, 3, 4],
                "b": [4, 3, 2, 1],
                "c": [1, 2, 3, 4],
            }
        )
        result = calculate_reliability(
            frame,
            ["a", "b", "c"],
            [],
            1,
            5,
            SamplingDesign.ORDINARY,
        )
        item_a = result.item_statistics.set_index("题项").loc["a"]
        self.assertEqual(item_a["CITC"], "不适用")
        self.assertEqual(item_a["删除题项后的 α"], "不适用")

    def test_ordinal_descriptives_include_frequencies_and_iqr(self):
        frame = pd.DataFrame({"likert": [1, 2, 2, 3, 4, None]})
        result = ordinal_descriptives(frame, ["likert"])
        summary = result.summary.iloc[0]
        self.assertEqual(summary["有效数"], 5)
        self.assertEqual(summary["缺失数"], 1)
        self.assertAlmostEqual(summary["IQR"], 1.0)
        self.assertEqual(int(result.frequencies["频数"].sum()), 5)


if __name__ == "__main__":
    unittest.main()
